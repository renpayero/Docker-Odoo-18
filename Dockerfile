FROM odoo:18.0

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        swig \
        libssl-dev \
        python3-dev \
        git \
        python3-pip \
        libjpeg-dev \
        zlib1g-dev \
        libfreetype6-dev \
        liblcms2-dev \
        libwebp-dev \
        postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN PIP_BREAK_SYSTEM_PACKAGES=1 pip3 install --no-cache-dir -r /tmp/requirements.txt

COPY entrypoint.sh /usr/local/bin/mp-entrypoint.sh
RUN chmod +x /usr/local/bin/mp-entrypoint.sh

USER odoo

ENTRYPOINT ["/usr/local/bin/mp-entrypoint.sh"]
CMD ["odoo"]
