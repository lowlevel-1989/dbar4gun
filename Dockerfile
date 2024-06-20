FROM python:slim AS build

COPY setup.py /opt/dbar4gun/setup.py
COPY dbar4gun /opt/dbar4gun/dbar4gun

RUN apt update -y && \
        apt install gcc -y && \
        pip install /opt/dbar4gun/


FROM python:slim

COPY --from=build /usr/local/lib    /usr/local/lib
COPY --from=build /usr/local/bin    /usr/local/bin

ENTRYPOINT dbar4gun
