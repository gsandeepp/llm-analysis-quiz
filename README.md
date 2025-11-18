# LLM Analysis Quiz Solver

FastAPI service that automatically solves quiz tasks with JavaScript rendering using Playwright.

## Features
- JavaScript rendering with Playwright
- PDF processing and data extraction
- Quiz chain following
- 3-minute timeout handling

## API Endpoints
- `GET /health` - Service status
- `GET /prompts` - Get system/user prompts  
- `POST /solve` - Main quiz solver
- `GET /wakeup` - Keep-alive endpoint

## Deployment
Deployed on Render.com for reliable performance.

## License
MIT
