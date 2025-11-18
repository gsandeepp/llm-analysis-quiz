# LLM Analysis Quiz Solver

FastAPI service that automatically solves quiz tasks by extracting data from PDFs and submitting answers.

## Features
- PDF processing and data extraction
- Quiz chain following
- 3-minute timeout handling
- Robust error handling

## API Endpoints
- `GET /health` - Service status
- `GET /prompts` - Get system/user prompts  
- `POST /solve` - Main quiz solver
- `GET /wakeup` - Keep-alive endpoint

## Deployment
Deployed on Railway for reliable performance.

## License
MIT
