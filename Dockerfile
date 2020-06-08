ARG ROSDISTRO=melodic
FROM ros:${ROSDISTRO}-ros-base

ARG DEBIAN_FRONTEND=noninteractive

# built-in packages
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        supervisor \
        openssh-server pwgen sudo vim-tiny \
        net-tools \
        lxde x11vnc xvfb \
        gtk2-engines-murrine ttf-ubuntu-font-family \
        nginx \
        python-pip python-dev build-essential \
        mesa-utils libgl1-mesa-dri \
        gnome-themes-standard gtk2-engines-pixbuf gtk2-engines-murrine pinta arc-theme \
        dbus-x11 x11-utils \
        terminator \
    && rm -rf /var/lib/apt/lists/*

# tini for subreap
ENV TINI_VERSION v0.19.0
ADD https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini /tini
RUN chmod +x /tini

ENV NOVNC_VERSION 1.1.0
RUN curl -sSL https://github.com/novnc/noVNC/archive/v${NOVNC_VERSION}.tar.gz | tar xz -C / && mv /noVNC-${NOVNC_VERSION} /noVNC

ADD image /
RUN pip install setuptools wheel && pip install -r /usr/lib/web/requirements.txt

RUN cp /usr/share/applications/terminator.desktop /root/Desktop
RUN echo "source /opt/ros/$ROS_DISTRO/setup.bash" >> /root/.bashrc

EXPOSE 80
WORKDIR /root
ENV SHELL=/bin/bash
ENTRYPOINT ["/startup.sh"]
