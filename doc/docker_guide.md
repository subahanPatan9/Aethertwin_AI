# AetherTwin: Docker Configuration Guide (Line-by-Line Explanation)

This document provides a detailed, line-by-line explanation of all the Docker files created in the project. This will help you understand exactly how the containerization works and answer any docker-related questions during your presentation.

---

## 1. Backend Dockerfile (`/backend/Dockerfile`)
This file packages the Python FastAPI backend and the physics simulation engine.

| Line of Code | What it Means / Why it is Used |
| :--- | :--- |
| `FROM python:3.11-slim` | **Base Image**: Starts the build from the official Python 3.11 image. The `-slim` version is chosen because it removes unnecessary packages, keeping the final container size small. |
| `WORKDIR /app` | **Working Directory**: Creates a folder named `/app` inside the container and sets it as the default folder for any subsequent commands. |
| `ENV PYTHONDONTWRITEBYTECODE=1` | **Environment Variable**: Tells Python not to write `.pyc` (compiled bytecode) files to the disk, keeping the container filesystem clean. |
| `ENV PYTHONUNBUFFERED=1` | **Environment Variable**: Ensures that Python console logs are printed immediately to the terminal in real time, preventing delay in debugging. |
| `RUN apt-get update && apt-get install -y --no-install-recommends build-essential ...` | **System Dependencies**: Updates the Linux package installer inside the container and installs basic C++ compilers (`build-essential`) which might be needed to compile some Python packages. Then it cleans up temporary installer files to keep the container light. |
| `COPY requirements.txt .` | **Copy Dependency List**: Copies only the `requirements.txt` file from your computer into the container's `/app` folder. (Done separately before copying code to cache layers and make future builds faster). |
| `RUN pip install --no-cache-dir -r requirements.txt` | **Install Packages**: Runs `pip` inside the container to install FastAPI, Uvicorn, and PyMongo. `--no-cache-dir` ensures pip doesn't save copies of downloaded files, reducing image size. |
| `COPY . .` | **Copy Source Code**: Copies all files from the backend directory on your computer (like `app.py`, `simulator.py`, `ai_model.py`, `db.py`) into the container. |
| `EXPOSE 8000` | **Documentation Port**: Exposes port `8000` to indicate that the FastAPI application is listening on this port inside the container. |
| `CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]` | **Startup Command**: Starts the FastAPI web server. `--host 0.0.0.0` is critical because it tells Uvicorn to listen to requests from outside the container (like the frontend container or host browser). |

---

## 2. Frontend Dockerfile (`/frontend/Dockerfile`)
This file uses a **Multi-Stage Build** to build the Angular application and then serve it using Nginx.

### Stage 1: Build the Angular app
| Line of Code | What it Means / Why it is Used |
| :--- | :--- |
| `FROM node:22-alpine AS build-stage` | **Base Image**: Starts the build using Node.js version 22. The `-alpine` tag indicates an extremely small Linux distribution (Alpine Linux) to save disk space. The `AS build-stage` labels this step so we can copy its output later. |
| `WORKDIR /app` | **Working Directory**: Sets `/app` as the active folder inside the build container. |
| `COPY package*.json ./` | **Copy Dependency List**: Copies `package.json` and `package-lock.json` into the `/app` directory. |
| `RUN npm ci` | **Clean Install**: Performs a clean installation of all node packages specified in `package.json`. It is faster and more deterministic than `npm install` for automated builds. |
| `COPY . .` | **Copy Source Code**: Copies the entire Angular project from your local computer into the build container. |
| `RUN npm run build` | **Build Command**: Runs the Angular compiler (`ng build`) inside the container. This compiles the TypeScript code into static optimized HTML, JS, and CSS files in the `dist/frontend/browser` folder. |

### Stage 2: Serve the compiled files using Nginx
| Line of Code | What it Means / Why it is Used |
| :--- | :--- |
| `FROM nginx:alpine` | **Nginx Web Server**: Starts a new, clean container using Nginx. The previous Node.js container (which is huge) is discarded, leaving only Nginx. |
| `COPY nginx.conf /etc/nginx/conf.d/default.conf` | **Custom Configuration**: Replaces Nginx's default server configuration with our custom `nginx.conf` so it supports Angular's routing pathways. |
| `COPY --from=build-stage /app/dist/frontend/browser /usr/share/nginx/html` | **Copy Assets**: Copies only the compiled static HTML, CSS, and JS files from the `build-stage` container (from Stage 1) and places them in Nginx's default web directory (`/usr/share/nginx/html`). |
| `EXPOSE 80` | **Documentation Port**: Exposes port `80` (the standard HTTP web server port) inside the container. |
| `CMD ["nginx", "-g", "daemon off;"]` | **Start Nginx**: Starts the Nginx web server in the foreground, keeping the container running. |

---

## 3. Nginx Configuration (`/frontend/nginx.conf`)
Nginx is a reverse-proxy and web server. Angular is a Single Page Application (SPA), meaning it only has one actual HTML file (`index.html`).

| Line of Code | What it Means / Why it is Used |
| :--- | :--- |
| `listen 80;` | Tells Nginx to listen for incoming web requests on port `80` (inside the container). |
| `server_name localhost;` | The domain name Nginx is responding to (default local host). |
| `root /usr/share/nginx/html;` | The folder where the index.html and compiled javascript files are stored. |
| `index index.html index.htm;` | The default file name Nginx should load when you open the homepage. |
| `try_files $uri $uri/ /index.html;` | **SPA Routing Support**: Very important! Tells Nginx: "If the user visits a subpath (like `/copilot` or `/analytics`), check if that file exists on the server. If it does not exist, do not return a 404 error; instead, redirect them back to `index.html`." This allows Angular to handle the routing internally. |

---

## 4. Docker Compose File (`/docker-compose.yml`)
Docker Compose lets you run and connect all three containers (MongoDB, FastAPI, and Angular) with a single command.

| Line of Code | What it Means / Why it is Used |
| :--- | :--- |
| `version: '3.8'` | Specifies the version of the Docker Compose schema we are using. |
| `services:` | Begins the definition of the individual containers. |
| **Service 1: `db`** | |
| `image: mongo:latest` | Uses the official MongoDB database image from Docker Hub. |
| `container_name: aethertwin_mongodb` | Names the running database container. |
| `ports: - "27017:27017"` | Maps port `27017` of your physical computer to port `27017` inside the database container. This allows you to connect using **MongoDB Compass** locally on your host machine. |
| `volumes: - mongo_data:/data/db` | **Data Persistence**: Mounts a Docker volume named `mongo_data` to `/data/db` inside the container. This ensures that even if the container is stopped or deleted, your database records (telemetry logs, settings) are not lost. |
| **Service 2: `backend`** | |
| `build: ./backend` | Tells Docker to navigate to the `/backend` folder and build the image using the `Dockerfile` inside it. |
| `ports: - "8000:8000"` | Maps port `8000` of the host computer to the container, so the frontend app can communicate with the APIs. |
| `environment: - MONGO_URI=mongodb://db:27017/` | **Connection Variable**: Sets `MONGO_URI` to point to `db` (which is the name of the database service container). Docker Compose automatically creates a local network where the hostname `db` resolves to the MongoDB container IP. |
| `depends_on: - db` | **Startup Order**: Tells Docker Compose to start the `db` container first before starting the `backend` container. |
| **Service 3: `frontend`** | |
| `build: ./frontend` | Tells Docker to navigate to the `/frontend` folder and build the image using the multi-stage `Dockerfile` inside it. |
| `ports: - "4200:80"` | Maps port `4200` of your physical computer to port `80` (Nginx) inside the container. This is why you open **`http://localhost:4200`** in your browser. |
| `depends_on: - backend` | **Startup Order**: Starts the `backend` server before starting the frontend server. |
