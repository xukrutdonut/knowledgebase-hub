FROM node:20-alpine AS builder

WORKDIR /app
COPY package.json ./
RUN npm install --omit=dev

COPY . .

# Descargar 3Dmol.js localmente (evita CDN externo en producción)
RUN wget -q "https://3Dmol.csb.pitt.edu/build/3Dmol-min.js" -O public/3Dmol-min.js || \
    wget -q "https://cdnjs.cloudflare.com/ajax/libs/3Dmol/2.1.0/3Dmol-min.js" -O public/3Dmol-min.js || \
    echo "WARN: 3Dmol no descargado, se usará CDN como fallback"

FROM node:20-alpine
WORKDIR /app
COPY --from=builder /app .
EXPOSE 3000
CMD ["node", "server.js"]
