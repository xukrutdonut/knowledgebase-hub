FROM nginx:alpine

# Descargar y descomprimir la release oficial de JBrowse 2 Web (ignorar warnings menores de unzip con || true)
RUN apk add --no-cache curl unzip && \
    curl -L -O https://github.com/GMOD/jbrowse-components/releases/download/v2.10.3/jbrowse-web-v2.10.3.zip && \
    unzip -q jbrowse-web-v2.10.3.zip -d /usr/share/nginx/html || true && \
    rm jbrowse-web-v2.10.3.zip

EXPOSE 80
