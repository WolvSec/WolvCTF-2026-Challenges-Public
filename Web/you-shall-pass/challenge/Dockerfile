FROM node:20-slim

WORKDIR /app

RUN npm init -y && npm install express@4.19.2

COPY server.js /app/server.js
COPY flag.txt /flag.txt
RUN chmod 0444 /flag.txt

USER node
EXPOSE 3000
CMD ["node", "server.js"]
