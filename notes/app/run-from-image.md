cd "D:\me\TMA AI\CatDogClassifier\src"

# 1. Build all five images (tagged with your registry name) (If any)

docker compose -f docker-compose-img.yml build

# 2. Push them to Docker Hub (If any)

docker login
docker compose -f docker-compose-img.yml push

# 3. Run everything from the published images

docker compose -f docker-compose-img.yml up -d
