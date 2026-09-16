FROM node:20-alpine

WORKDIR /app

# Copy only the package files first so Docker can cache the npm install layer
# it only reruns if package.json actually changes.
COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 5173

# --host 0.0.0.0 is required: by default Vite's dev server only listens on
# localhost *inside* the container, which your browser (outside the
# container) can't reach. This makes it listen on all interfaces.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]