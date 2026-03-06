FROM node:20-alpine

WORKDIR /app

COPY package.json /app/package.json
COPY apps/web/package.json /app/apps/web/package.json
COPY packages/ui/package.json /app/packages/ui/package.json
COPY packages/types/package.json /app/packages/types/package.json
COPY packages/config/package.json /app/packages/config/package.json

RUN npm install

COPY . /app

WORKDIR /app
