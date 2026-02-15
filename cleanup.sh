#!/bin/bash
echo "Docker cleanup..."

if command -v docker-compose >/dev/null 2>&1; then
  docker-compose down -v 2>/dev/null
  docker-compose -f docker-compose.secure.yml down -v 2>/dev/null
else
  docker compose down -v 2>/dev/null
  docker compose -f docker-compose.secure.yml down -v 2>/dev/null
fi

docker system prune -af --volumes 2>/dev/null
echo "Done"
