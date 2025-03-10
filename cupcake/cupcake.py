"""Cupcake S3 FastAPI."""
from pathlib import Path
import os
import asyncio
import re
import configparser
import json
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pydantic import BaseModel
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
# pylint: disable=line-too-long

BACKUP_SCRIPT = "/cupcake/cupcake.sh"
CRON_DIR = "/etc/cron.d"
LOG_DIR = "/var/log/cupcake"
AWS_CREDENTIALS_FILE = "/root/.aws/credentials"
AWS_CONFIG_FILE = "/root/.aws/config"
CLOUDFORMATION_DIR = "cloudformation"

FRONTEND_PATH = Path(__file__).parent
JS_PATH = FRONTEND_PATH / "js"
CSS_PATH = FRONTEND_PATH / "css"
IMG_PATH = FRONTEND_PATH / "img"
WEBFONTS_PATH = FRONTEND_PATH / "webfonts"
ACTIVE_WEBSOCKETS = set()

app = FastAPI()
app.mount("/js", StaticFiles(directory=JS_PATH), name="js")
app.mount("/css", StaticFiles(directory=CSS_PATH), name="css")
app.mount("/img", StaticFiles(directory=IMG_PATH), name="img")
app.mount("/webfonts", StaticFiles(directory=WEBFONTS_PATH), name="webfonts")

class CupcakeJob(BaseModel):
    """Model for backup cron job."""
    name: str
    schedule: str
    source: str
    destination: str
    profile: str
    storage_class: str

class Profile(BaseModel):
    """Model for AWS profile."""
    name: str
    aws_access_key_id: str
    aws_secret_access_key: str
    region: str
    role_arn: str

class JobsHandler(FileSystemEventHandler):
    """File system event handler for cron jobs."""
    def data(self):
        """Return websocket data."""
        return asyncio.run(websocket_data())

    def on_created(self, event):
        asyncio.run(notify_websockets(self.data()))

    def on_modified(self, event):
        asyncio.run(notify_websockets(self.data()))

    def on_deleted(self, event):
        asyncio.run(notify_websockets(self.data()))

def sanitize_path(*args):
    """Sanitize path."""
    return os.path.normpath(os.path.join(*args))

@app.get("/", response_class=FileResponse)
async def root_home():
    """Serves the cupcake."""
    return FileResponse(FRONTEND_PATH / "cupcake.html")

@app.get("/favicon.ico", response_class=FileResponse, include_in_schema=False)
async def favicon():
    """Serves the favicon."""
    return FileResponse(FRONTEND_PATH / "img/favicon.ico")

@app.get("/download/cupcake.yml", response_class=FileResponse)
async def download_cloudformation_template():
    """Downloads the CloudFormation template."""
    filename = "cupcake.yml"
    file_path = sanitize_path(FRONTEND_PATH, CLOUDFORMATION_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="CloudFormation template not found")
    return FileResponse(file_path, filename=filename, media_type="application/octet-stream")

@app.get("/api/health", response_class=JSONResponse)
async def api_health():
    """Health check."""
    return await get_health()

@app.get("/api/profiles", response_class=JSONResponse)
async def api_get_profiles():
    """Lists profiles."""
    return get_aws_profiles()

@app.get("/api/profile/{profile}", response_class=JSONResponse)
async def api_get_profile(profile: str):
    """Gets a profile."""
    return get_aws_profile(profile)

@app.post("/api/profile", response_class=JSONResponse)
async def api_add_profile(profile: Profile):
    """Adds a new profile."""
    profile_name = profile.name
    access_key_id = profile.aws_access_key_id
    secret_access_key = profile.aws_secret_access_key
    role_arn = profile.role_arn
    region = profile.region

    create_aws_profile(profile_name, access_key_id, secret_access_key, role_arn, region)
    return {"message": "Profile added successfully"}

@app.delete("/api/profile/{profile}", response_class=JSONResponse)
async def api_delete_profile(profile: str):
    """Deletes a profile."""
    delete_aws_profile(profile)
    return {"message": "Profile deleted successfully"}

@app.get("/api/jobs", response_class=JSONResponse)
async def api_get_jobs():
    """Lists jobs."""
    return await get_jobs()

@app.post("/api/job", response_class=JSONResponse)
async def api_add_job(job: CupcakeJob):
    """Adds a new job."""
    return create_job(job)

@app.delete("/api/job/{job}", response_class=JSONResponse)
async def api_delete_job(job: str):
    """Deletes a job."""
    return delete_job(job)

@app.get("/api/job/{job}/stats", response_class=JSONResponse)
async def api_get_stats(job: str):
    """Get stats for a job."""
    return get_stats(job)

@app.get("/api/job/{job}/logs", response_class=JSONResponse)
async def api_get_logs(job: str):
    """Get list of logs for a job."""
    return get_logs(job)

@app.get("/api/job/{job}/log/{num}", response_class=FileResponse)
async def api_get_log(job: str, num: int):
    """Get a log file."""
    log_file = f"{job}.log"
    if num > 0:
        log_file = f"{job}.log.{num}"
    return FileResponse(get_log(log_file))

@app.websocket("/api/job/{name}/log/latest")
async def logs_ws_endpoint(websocket: WebSocket, name: str):
    """WebSocket for tailing logs."""
    await websocket.accept()
    try:
        log_file = sanitize_path(LOG_DIR, f"{name}.log")
        await websocket.send_text(f"Tailing log file: {log_file} ...")
        process = await asyncio.create_subprocess_shell(
            f"tail -n 200 -F {log_file}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        while True:
            line = await process.stdout.readline()
            if not line:
                break
            await websocket.send_text(line.decode().strip())

    except FileNotFoundError:
        await websocket.send_text(f"Log file {log_file} not found.")
    except WebSocketDisconnect:
        print("Logs WebSocket disconnected")
    finally:
        if process and process.returncode is None:
            process.terminate()
            await process.wait()

@app.websocket("/ws/cupcake")
async def jobs_ws_endpoint(websocket: WebSocket):
    """WebSocket for jobs data."""
    # pylint: disable=broad-exception-caught
    await websocket.accept()
    ACTIVE_WEBSOCKETS.add(websocket)
    try:
        data = await websocket_data()
        await websocket.send_text(data)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        print("Jobs WebSocket disconnected")
        ACTIVE_WEBSOCKETS.remove(websocket)
    except Exception:
        print("Jobs WebSocket error")
        ACTIVE_WEBSOCKETS.remove(websocket)
    finally:
        try:
            await websocket.close()
        except RuntimeError:
            pass

@app.on_event("startup")
async def startup_event():
    """Startup event."""
    asyncio.create_task(asyncio.to_thread(start_file_watcher))
    asyncio.create_task(asyncio.to_thread(start_health_watcher))

async def websocket_data():
    """Returns data for websockets."""
    data = {
        "jobs": await get_jobs(),
        "health": await get_health()
    }
    return json.dumps(data)

async def notify_websockets(message: str):
    """Notify all connected websockets."""
    # pylint: disable=broad-exception-caught
    for websocket in list(ACTIVE_WEBSOCKETS):
        try:
            await websocket.send_text(message)
        except Exception:
            ACTIVE_WEBSOCKETS.remove(websocket)

def start_file_watcher():
    """Starts the file watcher."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    observer = Observer()
    observer.schedule(JobsHandler(), CRON_DIR, recursive=False)
    observer.schedule(JobsHandler(), LOG_DIR, recursive=False)
    observer.start()

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        observer.stop()
    finally:
        observer.join()
        loop.close()

def start_health_watcher():
    """Starts the health watcher."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(health_watcher())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()

async def health_watcher():
    """Watches the health of the system."""
    try:
        while True:
            data = await websocket_data()
            await notify_websockets(data)
            await asyncio.sleep(30)
    except asyncio.CancelledError:
        print("Health watcher cancelled")
    except KeyboardInterrupt:
        pass
    finally:
        print("Health watcher stopped")

def parse_cron_file(filepath):
    """Parses a cron file.

    Returns:
        dict: A dictionary containing schedule, user, source, destination, profile, and log_file.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            line = f.readline().strip()
    except FileNotFoundError:
        return {}

    if not line:
        return {}

    parts = line.split(maxsplit=6)  # Split into at most 6 parts
    if len(parts) < 6:
        return {}

    schedule = ' '.join(parts[:5])
    user = parts[5]
    command = parts[6]

    result = {
        'name': os.path.basename(filepath),
        'schedule': schedule,
        'user': user,
        'source': None,
        'destination': None,
        'profile': None,
        'log_retention': None,
        'storage_class': None,
        'delete': False,
        'log_file': None,
    }

    source_match = re.search(r"--source\s+(\S+)", command)
    if source_match:
        result['source'] = source_match.group(1)

    destination_match = re.search(r"--destination\s+(\S+)", command)
    if destination_match:
        result['destination'] = destination_match.group(1)

    profile_match = re.search(r"--profile\s+(\S+)", command)
    if profile_match:
        result['profile'] = profile_match.group(1)

    log_retention_match = re.search(r"--log-retention\s+(\S+)", command)
    if log_retention_match:
        result['log_retention'] = log_retention_match.group(1)

    storage_class_match = re.search(r"--storage-class\s+(\S+)", command)
    if storage_class_match:
        result['storage_class'] = storage_class_match.group(1)

    delete_match = re.search(r"--delete", command)
    if delete_match:
        result['delete'] = True

    log_match = re.search(r"[>]{1,2}\s*(\S+)\s*(?:2>&1)?$", command)
    if log_match:
        result['log_file'] = log_match.group(1)

    return result

async def get_health():
    """Checks the health of the system."""
    # pylint: disable=broad-exception-caught
    health = {
        'status': 'unknown',
        'crond': 'unknown',
    }
    try:
        process = await asyncio.create_subprocess_shell(
            "ps -e | grep crond",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _= await process.communicate()
        output = stdout.decode().strip()
        if output:
            health['crond'] = "running"
            health['status'] = "tasty"
        else:
            health['crond'] = "stopped"
            health['status'] = "spoiled"
    except Exception:
        health['crond'] = "unknown"
        health['status'] = "spoiled"
    health['msg'] = f"""
       <p class='m-0'><strong>Cupcake</strong> is {health['status']}.</p>
    """
    return health

async def get_stats(name: str):
    """Retrieves stats for a job."""
    stats_file = sanitize_path(LOG_DIR, f"{name}.stats")
    stats = {}
    if os.path.exists(stats_file):
        with open(stats_file, "r", encoding='utf-8') as f:
            try:
                stats = json.load(f)
            except json.JSONDecodeError:
                print(f"Error decoding JSON file {stats_file}")
    return stats

async def get_jobs():
    """Retrieves and parses cron entries."""
    entries = []
    try:
        for filename in os.listdir(CRON_DIR):
            filepath = sanitize_path(CRON_DIR, filename)
            if os.path.isfile(filepath):
                details = parse_cron_file(filepath)
                stats = await get_stats(details['name'])
                entries.append({**details, **stats})
    except FileNotFoundError:
        print(f"Directory {CRON_DIR} not found.")
    return entries

def create_job(job: CupcakeJob):
    """Creates a cron job."""
    name = job.name
    schedule = job.schedule
    log_file = sanitize_path(LOG_DIR, f"{name}.log")
    stats_file = sanitize_path(LOG_DIR, f"{name}.stats")

    command_arguments = {
        "--source": job.source,
        "--destination": job.destination,
        "--log-retention": "3",
        "--profile": job.profile,
        "--storage-class": job.storage_class,
        "--delete": ""
    }

    user = "root"
    cron_file = sanitize_path(CRON_DIR, name)

    command_args = ""
    for key, value in command_arguments.items():
        if isinstance(value, bool):
            command_args += f"{key} "
        else:
            command_args += f"{key} {value} "

    cron_job = f'{schedule} {user} {BACKUP_SCRIPT} {command_args} >> {log_file} 2>&1'

    try:
        with open(cron_file, "w", encoding='utf-8') as f:
            f.write(f"{cron_job}\n")
        with open(stats_file, "w", encoding='utf-8') as f:
            json.dump({"uploaded": 0, "deleted": 0, "downloaded": 0, "last_run": 0}, f)
        return {"message": "Job added successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

def delete_job(name: str):
    """Deletes a cron job."""
    cron_file = sanitize_path(CRON_DIR, name)
    try:
        os.remove(cron_file)
        for filename in os.listdir(LOG_DIR):
            if filename.startswith(name):
                os.remove(sanitize_path(LOG_DIR, filename))
        return {"message": "Job deleted successfully"}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail="Job not found") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

def get_logs(name: str):
    """Retrieves logs for a job.

    Example: job.log job.log.1 job.log.2
    """
    logs = []
    for filename in os.listdir(LOG_DIR):
        if filename.startswith(f"{name}.log"):
            logs.append(sanitize_path(LOG_DIR, filename))
    return {"name": name, "count": len(logs), "logs": list(reversed(logs))[1:]}

def get_log(log_file: str):
    """Retrieves a log file."""
    return sanitize_path(LOG_DIR, log_file)

def aws_configuration_paths():
    """
    Get the paths to the AWS credentials and config files.

    Returns:
        tuple: A tuple containing the paths to the credentials and config files.
    """

    credentials_path = os.path.expanduser("~/.aws/credentials")
    config_path = os.path.expanduser("~/.aws/config")

    return (credentials_path, config_path)

def read_aws_configurations():
    """
    Load and open the AWS credentials and config files.

    Returns:
        tuple: A tuple containing the credentials and config files.
    """

    credentials_path, config_path = aws_configuration_paths()

    credentials_config = configparser.ConfigParser()
    config_config = configparser.ConfigParser()

    if not os.path.exists(credentials_path):
        Path(credentials_path).touch()

    if not os.path.exists(config_path):
        Path(config_path).touch()

    credentials_config.read(credentials_path)
    config_config.read(config_path)

    return (credentials_config, config_config)


def get_config_profile_name(profile_name):
    """
    Get the profile name for the AWS config file.

    Args:
        profile_name (str): The profile name.

    Returns:
        str: The profile name for the AWS config file.
    """

    return f"profile {profile_name}"

def get_aws_profiles():
    """
    Get all AWS profiles from ~/.aws/credentials and ~/.aws/config.

    Returns:
        list: A list of dictionaries containing the profiles' credentials and config.
    """

    credentials_config, _ = read_aws_configurations()
    profiles = []
    for profile in credentials_config.sections():
        profiles.append(get_aws_profile(profile))

    return profiles

def get_aws_profile(profile_name: str):
    """
    Get an AWS profile from ~/.aws/credentials and ~/.aws/config.

    Args:
        profile_name (str): The name of the AWS profile.

    Returns:
        dict: A dictionary containing the profile's credentials and config.
    """
    config_profile_name = get_config_profile_name(profile_name)
    credentials_config, config_config = read_aws_configurations()

    if profile_name not in credentials_config.sections() or config_profile_name not in config_config.sections():
        return {"error": "Profile not found."}

    profile = {"name": profile_name}
    properties = ["aws_access_key_id", "aws_secret_access_key", "role_arn", "region"]
    for prop in properties:
        if credentials_config.has_option(profile_name, prop):
            profile[prop] = credentials_config.get(profile_name, prop)
        if config_config.has_option(config_profile_name, prop):
            profile[prop] = config_config.get(config_profile_name, prop)

    return profile

def create_aws_profile(profile_name: str, access_key_id: str, secret_access_key: str, role_arn: str, region: str):
    """
    Creates or updates an AWS profile in both ~/.aws/credentials and ~/.aws/config.

    Args:
        profile_name (str): The name of the AWS profile.
        access_key_id (str): The AWS access key ID.
        secret_access_key (str): The AWS secret access key.
        role_arn (str, optional): The ARN of the IAM role to assume. Defaults to None.
        region (str, optional): The AWS region. Defaults to None.
    """
    config_profile_name = get_config_profile_name(profile_name)
    credentials_path, config_path = aws_configuration_paths()

    # Create or update credentials file
    credentials_config = configparser.ConfigParser()
    if os.path.exists(credentials_path):
        credentials_config.read(credentials_path)

    if profile_name not in credentials_config:
        credentials_config.add_section(profile_name)

    # Create or update config file
    config_config = configparser.ConfigParser()
    if os.path.exists(config_path):
        config_config.read(config_path)

    if config_profile_name not in config_config:
        config_config.add_section(config_profile_name)

    credentials_config.set(profile_name, "aws_access_key_id", access_key_id)
    credentials_config.set(profile_name, "aws_secret_access_key", secret_access_key)

    config_config.set(config_profile_name, "role_arn", role_arn)
    config_config.set(config_profile_name, "region", region)
    config_config.set(config_profile_name, "source_profile", profile_name)
    config_config.set(config_profile_name, "output", "json")

    with open(credentials_path, "w", encoding='utf-8') as configfile:
        credentials_config.write(configfile)

    with open(config_path, "w", encoding='utf-8') as configfile:
        config_config.write(configfile)

def delete_aws_profile(profile_name):
    """
    Deletes an AWS profile from ~/.aws/credentials and ~/.aws/config.

    Args:
        profile_name (str): The name of the AWS profile.
    """

    config_profile_name = get_config_profile_name(profile_name)
    credentials_path, config_path = aws_configuration_paths()
    credentials_config, config_config = read_aws_configurations()

    if profile_name in credentials_config:
        credentials_config.remove_section(profile_name)
        with open(credentials_path, "w", encoding='utf-8') as configfile:
            credentials_config.write(configfile)

    if config_profile_name in config_config:
        config_config.remove_section(config_profile_name)
        with open(config_path, "w", encoding='utf-8') as configfile:
            config_config.write(configfile)
