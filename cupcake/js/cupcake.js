const { createApp, ref, computed, onMounted } = Vue;

createApp({
    setup() {
        const title = ref("Cupcake S3");
        const githubUrl = ref('https://github.com/napalm255/cupcake-s3');

        const currentPage = ref("Start");
        const currentHash = ref('#/start');
        const health = ref("");
        const jobs = ref([]);
        const logs = ref([]);
        const profiles = ref([]);
        const logContent = ref("");
        const modalJobVisible = ref(false);
        const modalProfileVisible = ref(false);
        const showingLog = ref("");
        const tooltipTriggerList = ref([]);
        const tooltipList = ref([]);
        const serverHost = computed(() => window.location.hostname);
        const serverPort = computed(() => window.location.port || (window.location.protocol === 'https:' ? '443' : '80'));
        const serverWsProtocol = computed(() => window.location.protocol === 'https:' ? 'wss:' : 'ws:');
        let socket = null
        let cupcakeSocket = null
        let reconnectInterval = 10000; // Initial delay

        const navBar = ref([
          'Jobs',
          'Profiles'
        ]);

        const newJobDefaults = ref({
          name: "",
          schedule: "*/30 * * * *",
          source: "",
          destination: "",
          profile: "",
          storage_class: "STANDARD_IA",
          resolved_schedule: cronstrue.toString("*/30 * * * *")
        });

        const newJob = ref({
          name: newJobDefaults.value.name,
          schedule: newJobDefaults.value.schedule,
          source: newJobDefaults.value.source,
          destination: newJobDefaults.value.destination,
          profile: newJobDefaults.value.profile,
          storage_class: newJobDefaults.value.storage_class,
          resolved_schedule: newJobDefaults.value.resolved_schedule
        });

        const newProfile = ref({
          name: "",
          aws_access_key_id: "",
          aws_secret_access_key: "",
          region: "",
          role_arn: ""
        });

        const showJobModal = () => {
          modalJobVisible.value = true;
          const resolvedSchedule = document.querySelector('.resolved-schedule');
          resolvedSchedule.innerHTML = newJobDefaults.value.resolved_schedule;
        };

        const hideJobModal = () => {
          modalJobVisible.value = false;
          newJob.value.name = newJobDefaults.value.name;
          newJob.value.schedule = newJobDefaults.value.schedule;
          newJob.value.source = newJobDefaults.value.source;
          newJob.value.destination = newJobDefaults.value.destination;
          newJob.value.profile = newJobDefaults.value.profile;
          newJob.value.storage_class = newJobDefaults.value.storage_class;
          const resolvedSchedule = document.querySelector('.resolved-schedule');
          resolvedSchedule.innerHTML = newJobDefaults.value.resolved_schedule;
        };

        const showProfileModal = () => {
          modalProfileVisible.value = true;
        }

        const hideProfileModal = () => {
          modalProfileVisible.value = false;
          newProfile.value.name = '';
          newProfile.value.aws_access_key_id = '';
          newProfile.value.aws_secret_access_key = '';
          newProfile.value.region = '';
          newProfile.value.role_arn = '';
        }

        const updateHash = async () => {
          currentHash.value = window.location.hash;
          switch (currentHash.value) {
            case '#/home':
              switchPage('Home');
              break;
            case '#/jobs':
              switchPage('Jobs');
              break;
            case '#/profiles':
              switchPage('Profiles');
              break;
            default:
              switchPage('Start');
          }
        }

        const switchPage = async (page) => {
          const homePage = document.getElementById('home');
          const jobsPage = document.getElementById('jobs');
          const profilesPage = document.getElementById('profiles');
          switch (page) {
            case "Start":
              if (jobs.value.length === 0 && profiles.value.length === 0) {
                switchPage('Home')
              } else {
                switchPage('Jobs')
              }
              break;
            case "Home":
              currentPage.value = "Home";
              homePage.style.display = 'block';
              jobsPage.style.display = 'none';
              profilesPage.style.display = 'none';
              window.location.hash = '#/home';
              currentHash.value = '#/home';
              break;
            case "Jobs":
              currentPage.value = "Jobs";
              homePage.style.display = 'none';
              jobsPage.style.display = 'block';
              profilesPage.style.display = 'none';
              window.location.hash = '#/jobs';
              currentHash.value = '#/jobs';
              break;
            case "Profiles":
              currentPage.value = "Profiles";
              homePage.style.display = 'none';
              jobsPage.style.display = 'none';
              profilesPage.style.display = 'block';
              window.location.hash = '#/profiles';
              currentHash.value = '#/profiles';
              break;
          }
        }

        const cupcakeSprinkles = async () => {
          const wsProtocol = await serverWsProtocol();
          if (cupcakeSocket) {
            cupcakeSocket.close();
          }

          cupcakeSocket = new WebSocket(`${wsProtocol}://${serverHost}:${serverPort}/ws/cupcake`);
          // console.log('Cupcake WebSocket created', cupcakeSocket);

          cupcakeSocket.onmessage = (event) => {
            jobs.value = JSON.parse(event.data).jobs;
            jobs.value.forEach(async (job) => {
              job.last_run_ago = await formattedLastRun(job.last_run);
            });
            health.value = JSON.parse(event.data).health;
          };

          cupcakeSocket.onclose = () => {
            // console.log('Cupcake WebSocket closed');
            setTimeout(cupcakeSprinkles, reconnectInterval);
            reconnectInterval = Math.min(reconnectInterval * 2, 30000); // Double, max 30s
          };

          cupcakeSocket.onerror = (error) => {
            console.error('Cupcake WebSocket error:', error);
          };
        };

        const resolveCron = (event) => {
          const resolvedSchedule = document.querySelector('.resolved-schedule');
          try {
            resolvedSchedule.innerHTML = cronstrue.toString(event.target.value);
          } catch (error) {
            resolvedSchedule.innerHTML = '<div class="spinner-border spinner-border-sm" role="status"><span class="visually-hidden">Loading...</span></div>';
          }
        };

        const getProfiles = async () => {
          await fetch("/api/profiles", {
            method: 'GET'
          })
          .then((response) => response.json())
          .then((data) => {
            profiles.value = data;
          })
          .catch((error) => console.error("Error fetching profiles:", error));
        };

        const addProfile = async () => {
          await fetch('/api/profile', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              name: newProfile.value.name,
              aws_access_key_id: newProfile.value.aws_access_key_id,
              aws_secret_access_key: newProfile.value.aws_secret_access_key,
              region: newProfile.value.region,
              role_arn: newProfile.value.role_arn
            })
          })
          .then(response => response.json())
          .then(data => {
            if (data.message) {
              hideProfileModal();
              getProfiles();
            } else {
              console.error('Error adding profile:', newProfile.value.name);
            }
          })
          .catch(error => {
            console.error('Error adding profile:', error);
          });
        };

        const deleteProfile = async (profile) => {
          await fetch(`/api/profile/${profile}`, {
            method: 'DELETE'
          })
          .then(response => response.json())
          .then(data => {
            if (data.message) {
              getProfiles();
            } else {
              console.error('Error deleting profile:', profile);
            }
          })
          .catch(error => {
            console.error('Error deleting profile:', error);
          });
        }

        const addJob = async () => {
          await fetch('/api/job', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              name: newJob.value.name,
              schedule: newJob.value.schedule,
              source: newJob.value.source,
              destination: newJob.value.destination,
              profile: newJob.value.profile,
              storage_class: newJob.value.storage_class
            })
          })
          .then(response => response.json())
          .then(data => {
            if (data.message) {
              hideJobModal();
              cupcakeSprinkles();
            } else {
              console.error('Error adding job:', newJob.value.job);
            }
          })
          .catch(error => {
            console.error('Error adding job:', error);
          });
        };

        const deleteJob = async (job) => {
          await fetch(`/api/job/${job}`, {
            method: 'DELETE'
          })
          .then(response => response.json())
          .then(data => {
            if (data.message) {
              cupcakeSprinkles();
            } else {
              console.error('Error deleting job:', job);
            }
          })
          .catch(error => {
            console.error('Error deleting job:', error);
          });
        };

        const toggleLog = async (job) => {
          const logDisplay = document.querySelector('.log-display');
          switch(logDisplay.style.display) {
            case 'block':
              logDisplay.style.display = 'none';
              await clearLog();
              break;
            case 'none':
              logDisplay.style.display = 'block';
              await clearLog();
              await getLogs(job);
              showLog(job, logDisplay);
              break;
            default:
              logDisplay.style.display = 'block';
              await clearLog();
              await getLogs(job);
              showLog(job, logDisplay);
          }
        }

        const getLogs = async (job) => {
            await fetch(`/api/job/${job}/logs`, {
                method: 'GET'
            })
            .then(response => response.json())
            .then(data => {
                logs.value = data;
            })
            .catch(error => {
                console.error('Error fetching logs:', error);
            });
            }

        const showLog = async (job, logDisplay) => {
          const wsProtocol = await serverWsProtocol();
          if (socket) {
            socket.close();
          }

          showingLog.value = job;
          logContent.value = '';
          socket = new WebSocket(`{${wsProtocol}://${serverHost}:${serverPort}/api/job/${job}/log/latest`);
          // console.log('WebSocket created', socket);

          socket.onmessage = (event) => {
            logContent.value += event.data + '\n';
            if (logDisplay) {
                logDisplay.scrollTop = logDisplay.scrollHeight;
            }
          };

          socket.onclose = () => {
            // console.log('WebSocket closed');
          };

          socket.onerror = (error) => {
            console.error('WebSocket error:', error);
          };
        };

        const clearLog = async () => {
          const oldLogsHeader = document.querySelectorAll('.oldlog-header');
          const oldLogsLog = document.querySelectorAll('.oldlog-log');
          const oldLogsContent = document.querySelectorAll('.oldlog-content');
          showingLog.value = '';
          logContent.value = '';
          oldLogsHeader.forEach((header) => {
            header.classList.add('collapsed');
          });
          oldLogsLog.forEach((log) => {
            log.classList.remove('show');
          });
          oldLogsContent.forEach((log) => {
            log.innerHTML = '';
          });
          if (socket) {
            socket.close();
          }
        }

        const showJobLog = async (job, idx) => {
          const accordionLog = document.querySelector('#logbody-' + idx);
          await fetch(`/api/job/${job}/log/${idx}`, {
            method: 'GET'
          })
          .then(response => response.text())
          .then(data => {
            accordionLog.textContent = data;
          })
          .catch(error => {
            console.error('Error fetching log:', error);
          });
        };

        const toggleDetails = (job) => {
          toggleLog(job);
        };

        const selectedJob = computed(() => {
          if (!showingLog.value) {
            return {uploaded: 0, downloaded: 0, deleted: 0};
          }
          return jobs.value.filter(item => item.name === showingLog.value)[0];
        });

        const formattedLastRun = async (lastRun) => {
          const now = new Date();
          const diff = Math.floor((now.getTime() / 1000) - lastRun); // Difference in seconds

          if (diff < 60) {
            return `${diff} seconds ago`;
          } else if (diff < 3600) {
            const minutes = Math.floor(diff / 60);
            return `${minutes} minute${minutes > 1 ? "s" : ""} ago`;
          } else if (diff < 86400) {
            const hours = Math.floor(diff / 3600);
            return `${hours} hour${hours > 1 ? "s" : ""} ago`;
          } else if (diff < 2592000) { // Approx 30 days
            const days = Math.floor(diff / 86400);
            return `${days} day${days > 1 ? "s" : ""} ago`;
          } else if (diff < 31536000) { // Approx 12 months
            const months = Math.floor(diff / 2592000);
            return `${months} month${months > 1 ? "s" : ""} ago`;
          } else {
            const years = Math.floor(diff / 31536000);
            return `${years} year${years > 1 ? "s" : ""} ago`;
          }
        };

        onMounted(async () => {
          await cupcakeSprinkles();
          await getProfiles();
          await switchPage('Start');
          window.addEventListener('hashchange', updateHash);
          tooltipTriggerList.value = document.querySelectorAll('[data-bs-toggle="tooltip"]');
          tooltipList.value = [...tooltipTriggerList.value].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
        });

        return {
          title, githubUrl, navBar, switchPage, currentPage,
          health, jobs, profiles, logs, showingLog,
          logContent, toggleDetails, selectedJob,
          newJob, modalJobVisible, showJobModal, hideJobModal, showJobLog, resolveCron,
          newProfile, modalProfileVisible, showProfileModal, hideProfileModal,
          getProfiles, addProfile, deleteProfile,
          addJob, deleteJob,
          tooltipTriggerList, tooltipList
        };
    }
}).mount("#app");

