<p align="center">
  <img src="https://raw.githubusercontent.com/napalm255/cupcake-s3/refs/heads/main/cupcake/img/logo.png" alt="Cupcake S3" width="240" height="239">
</p>
<p align="center">
<h1>Cupcake S3</h1>
</p>

[![Release](https://github.com/napalm255/cupcake-s3/actions/workflows/release.yml/badge.svg)](https://github.com/napalm255/cupcake-s3/actions/workflows/release.yml)
[![Pylint](https://github.com/napalm255/cupcake-s3/actions/workflows/pylint.yml/badge.svg)](https://github.com/napalm255/cupcake-s3/actions/workflows/pylint.yml)
[![CodeFactor](https://www.codefactor.io/repository/github/napalm255/cupcake-s3/badge)](https://www.codefactor.io/repository/github/napalm255/cupcake-s3)

Your sweet solution for managing transfers to and from your AWS S3 buckets.
Imagine it as your personal bakery for data!
You can bake up scheduled transfer jobs, setting them to rise at just the right time, and frost them with secure AWS credential profiles.
No more messy data spills! Cupcake S3 makes your S3 management a piece of cake... or should we say, a piece of cupcake!

## Features

* Easy to use web interface
* Schedule cron jobs to sync data to or from S3 buckets
* View job logs and basic statistics
* Manage multiple profiles for different S3 buckets


## Quick Setup

1. Install Docker and Docker-Compose

- [Docker Install documentation](https://docs.docker.com/install/)
- [Docker-Compose Install documentation](https://docs.docker.com/compose/install/)

2. Create a docker-compose.yml file similar to this:

```yml
services:
  cupcake-s3:
    container_name: cupcake-s3
    image: ghcr.io/napalm255/cupcake-s3:latest
    restart: unless-stopped
    ports:
      - 3124:3124
    volumes:
      - /mnt/media:/mnt/media:ro
      - ./cron:/etc/cron.d
      - ./creds:/root/.aws
      - ./logs:/var/log/cupcake
    environment:
      - TZ=America/New_York
```
To preserve your jobs and profiles, it is important to define volumes for the `/etc/cron.d` and `/root/.aws` folders.
The logs folder is optional but recommended for debugging purposes and to preserve the logs and statistics of your jobs.
You should have at least one mount for the data you want to sync.
In this example, we are mounting the `/mnt/media` directory as read-only, so the container can sync data from it to S3.
For jobs that sync data from S3 to your local directory, you can mount the directory as read-write.

3. Bring up your stack by running

```bash
docker-compose up -d

# If using docker-compose-plugin
docker compose up -d

```

4. Log in to the Cupcake UI

When your docker container is running, connect to it on port `3124` for the web interface interface.

[http://127.0.0.1:3124](http://127.0.0.1:3124)

On first login (and if you haven't setup a job or profile yet), you will be directed to the home page where you can find steps to setup your first job and profile.


## Setup AWS with CloudFormation

**Let's get started:**

1.  **Sign in to the AWS Management Console:**

    * Open your web browser and go to the AWS Management Console: [https://aws.amazon.com/console/](https://aws.amazon.com/console/)
    * Log in with your AWS account credentials.

2.  **Navigate to CloudFormation:**

    * In the AWS Management Console, type "CloudFormation" in the search bar and select it from the results.

3.  **Create a new stack:**

    * Click the `Create stack` button and select `With new resources (standard)`.
    * In the "Prepare template" section, select `Choose an existing template`.
    * In the "Template source" section, select `Upload a template file`.
    * Click `Choose file` and select the `cupcake.yml` file you want to use.
    * Click `Next`.

4.  **Specify stack details:**

    * **Stack name:** Give your stack a descriptive name (e.g., `cupcake-s3-deployment`).
    * **Parameters:**
        * **BucketName:** Optionally enter a unique name for your S3 bucket (e.g., `cupcake-s3-yourname`). If you leave this field blank, CloudFormation will generate a random name.
        * **CreateBucket:** Choose `true` to create a new bucket, or `false` to use an existing one.
        * **UserName:** Optionally enter a name for the IAM user (e.g., `cupcake-s3-user`). If you leave this field blank, CloudFormation will generate a random name.
        * **EnableIPRestriction:** Choose `true` to restrict access to a specific IP range, or `false` to allow access from anywhere.
        * **AllowedIPRange:** If you enabled IP restriction, enter the allowed IP range in CIDR notation (e.g., `192.168.1.0/24`). This needs to be your public IP address or the IP address range you want to allow. You can obtain your public IP address by visiting [https://checkip.amazonaws.com/](https://checkip.amazonaws.com/).
    * Click `Next`.

5.  **Configure stack options:**

    * On the "Configure stack options" page, you can optionally add tags, set permissions, or configure advanced options. For now, you can leave these settings as default.
    * Under `Capabilities`, check the box to `acknowledge that CloudFormation might create IAM resources with custom names`.
    * Click `Next`.

6.  **Review and create:**

    * Review your stack details and make sure everything is correct.
    * Click `Submit`.

7.  **Monitor stack creation:**

    * CloudFormation will start creating the resources defined in your template.
    * You can monitor the progress in the "Events" tab.
    * Wait for the stack status to change to `CREATE_COMPLETE`. This may take a few minutes.

**Gathering information from the output console:**

1.  **Retrieve the necessary information:**

    * Once the stack creation is complete, select your stack in the CloudFormation console.
    * Click on the `Outputs` tab.
    * In the `Outputs` tab, you'll find the following values:
        * **BucketName:** The name of your S3 bucket.
        * **IAMRoleArn:** The ARN of the IAM role.
        * **AccessKeyId:** The access key ID for the IAM user.
        * **SecretAccessKey:** The secret access key for the IAM user.
    * Take note of that information, as you will need this to configure Jobs and Profiles in Cupcake S3.

**Important notes:**

* Treat your access keys and secret keys like passwords. Do not share them or expose them in your client facing code.

## Getting Support

1. [Found a bug?](https://github.com/napalm255/cupcake-s3/issues)
