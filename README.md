# ytaudiodl
YooToob downloader for audio files.

This is the basis for an UnRaid Docker app.

### Usage
The front-end via Unraid's Docker apps will take a url and save as a replaygain-ed mp3.
If the URL refers to a full album with chapters, the output will a multi-mp3 download.

A `Download` button will allow you save the single file or zip file (multi-output).

### Config
For Unraid, point it at your Audio/Media directory to save output.

#### Unraid
- Docker -> Add Container
  - Template from `avbox` and adjust port(s) and volume mounts as needed.
#### Github
- Credentials for DockerHub
  - <repo>/settings/secrets/actions
    - DOCKER_USERNAME
    - DOCKER_PASSWORD
- setup GH Actions using the `docker-image.yml` template

### Requirements
Unraid.  But this Python file can be used via CLI with few changes.
Github to store the container image (built with Github Actions).


### References
- https://selfhosters.net/docker/templating/templating/
- https://github.com/binhex/docker-templates


