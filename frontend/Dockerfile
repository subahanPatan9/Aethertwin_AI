# Stage 1: Build the Angular application
FROM node:22-alpine AS build-stage

# Set working directory
WORKDIR /app

# Copy package.json and package-lock.json first to cache layers
COPY package*.json ./

# Install npm packages
RUN npm ci

# Copy the rest of the application files
COPY . .

# Build the Angular application in production mode
RUN npm run build

# Stage 2: Serve the application using Nginx
FROM nginx:alpine

# Copy custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy compiled static assets from the build stage to Nginx directory
COPY --from=build-stage /app/dist/frontend/browser /usr/share/nginx/html

# Expose port 80
EXPOSE 80

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]
