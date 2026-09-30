# 2026_ECGI_Data_Challenge
## Background
During the [2026 ECGI summit in Valencia spain](https://ecgisummit.com/ecgi-summit-2026), the winner of the 2026 ECGI data challenge will be announced. This repo contains the code for metrics used to evaluate submissions. Each dataset has a custom goal or target metric. These metrics are normalized into a final score across all datasets.

For more information about the challenge, please refer to the challenge webpag: <https://www.ecg-imaging.org/community/ecgi-data-challenge>


## Building App locally

### Requirements

  - Docker (e.g., [Docker desktop](https://www.docker.com/products/docker-desktop/))
  - Python (tested with Python 3.10)
  - Python libraries in [requirements.txt](https://github.com/CECGImaging/2026_ECGI_Data_Challenge/blob/main/requirements.txt)
 
 ### Configure Docker build
 
 The Docker container and Web app need to be configure to build and run properly in a local environment.  The primary configuration is in the `.env` file, but the `docker-compose.yml` may also need to be modified to match the environment. 
 
  1. *env file* - Copy the `example.env` and give it a relavent name, such as `.env`. Change or add the the following values to the env file:  
    - `AUTH_ENABLED=false`
    - `APP_BASE_URL=http://localhost:8100`
    - `SESSION_SECRET=[anything else.  Do not share]` (optional but recommended)
    - `ECGI_GT_UTAH_HOST=[/Path/to/Utah/GroundTruth/data]`
    - `ECGI_GT_AUCKLAND_HOST=[/Path/to/Auckland/GroundTruth/data]`
    - `ECGI_GT_HALIFAX_HOST=[/Path/to/Halifax/GroundTruth/data]`
    - `ECGI_GT_BRATISLAVA_HOST=[/Path/to/Bratislava/GroundTruth/data]`
  2. *docker-compose.yml* - Should not need to be changed if following the previous instructions.  However, make sure the following values match changes in previous steps:
    - `env_file:` needs to match the env file name in step 1. 
    
 
 ### Build Docker container
 
 With the build configure properly, building and deploying the app is simple with docker compose.  Use the following command in the terminal:
```
docker compose up --build
```
This iwll launch the app and run in the terminal window that you are running.  You will see the messages in the same window.  

To launch the container detached, add `-d` flag: 
```
docker compose up --build -d
```
The container and app will run in the background.  To see the logs of the container, use:
```
docker logs ecgi 
```
where `ecgi` is the name of the container set in `docker-compose.yml`.  This will show all the messages and logs of the app and the container.  These logs are also visible through the docker desktop app.  

The settings described in this section will configure the UI of the app to run at the url: `http://localhost:8099`. 

### Test locally
 
Past the `http://localhost:8099` url in a browser window to run the local app UI. The authorization is disabled in this configuration, but the backend code will be testable.  

The app FastAPI documentation is available at the `/docs` sub url, i.e., `http://localhost:8099/docs`.   


## TODO:
* Add example code for formatting submissions
* Add example code for running evaluation metrics on training data
* Add links to challenge site, data site, etc
* Add instructions about documenting methods and participating in the challenge consensus paper



## Contact Info:
The organizing committee for the 2026 ECGI challenge consists (so far) of:
Jake Bergquist,
Jess Tate, 
(others on CEI exec but need to get a list of who wants to be listed here)

Contact Jake (jbergquist@sci.utah.edu) for more info
