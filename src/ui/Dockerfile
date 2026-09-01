# Build the Angular app (production config -> container ports 8100-8103).
FROM node:22-alpine AS build
WORKDIR /app

# Install deps first (cached unless package*.json changes).
COPY package.json package-lock.json ./
RUN npm ci

# Copy sources and build. `npm run build` = `ng build --configuration production`,
# which file-replaces environment.ts with environment.production.ts.
COPY . .
RUN npm run build

# Serve the static bundle (SPA) behind nginx.
FROM nginx:alpine
COPY --from=build /app/dist/ui/browser /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 4200