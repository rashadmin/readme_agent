# Hospital Agent

> A reactive AI agent built with LangGraph that processes requests from Redis streams.

## 🧠 Overview

The Hospital Agent is a sophisticated AI agent designed to operate in a distributed system environment. It leverages LangGraph to maintain state and process tasks, continuously listening to Redis streams for incoming requests. This architecture allows the agent to be highly responsive and manage a queue of diverse requests, acting as a central processing unit for various hospital-related tasks or data.

## 🔨 What I Built

This project delivers a reactive agent capable of:

- **Redis Stream Integration:** Continuously monitors a designated Redis stream for new requests using a dedicated background thread, ensuring real-time task ingestion.
- **Stateful Processing with LangGraph:** Utilizes LangGraph's `StateGraph` to manage the agent's internal state, including a queue of incoming requests and associated metadata.
- **Conditional Response Generation:** Features a `responder` node within the graph that intelligently decides whether to send a response based on specific conditions within the agent's context.
- **Modular and Extensible Architecture:** Designed with clear separation of concerns, exposing the core graph object for easy integration into larger applications.

## 💭 Thought Process

My primary goal was to create an agent that could asynchronously handle a continuous flow of tasks without blocking. I decided to use LangGraph for its state management capabilities, as it provides a robust framework for defining complex agent behaviors and transitions. To address the challenge of ingesting requests from an external system like Redis streams, I opted for a background thread. This allows the agent to actively listen for new requests without halting the main graph execution, feeding the incoming data directly into the LangGraph state.

A key design decision was to implement a `responder` node that conditionally sends responses. This ensures that the agent only communicates back when a specific processing stage is complete or a particular condition is met. The `add` function was chosen as a reducer to efficiently manage the list of incoming requests within the agent's state, preventing state bloat and ensuring ordered processing. While the integration of a background thread with LangGraph introduced complexities around shared state management and thread safety, I focused on clearly defining how state updates occur to maintain consistency.

## 🛠️ Tools & Tech Stack

| Layer      | Technology               |
|------------|--------------------------|
| Language   | Python 3.x               |
| Framework  | LangGraph                |
| AI / LLM   | LangChain Core           |
| Messaging  | Redis                    |
| Testing    | pytest, AnyIO            |
| Utilities  | typing_extensions, dataclasses, threading, time |
| Observability | LangSmith (for tracing) |

## 🚀 Getting Started

### Prerequisites
- Python 3.x
- Redis server running locally or accessible via network.

### Installation

```bash
git clone https://github.com/username/hospital_agent.git # Replace username with actual
cd hospital_agent
pip install -r requirements.txt # Assuming a requirements.txt exists
```

### Environment Variables

While not explicitly defined in the provided summaries, based on the use of Redis, you might need to configure environment variables for Redis connection:

```env
REDIS_HOST=localhost
REDIS_PORT=6379
LANGCHAIN_TRACING_V2=true # For LangSmith tracing
LANGCHAIN_API_KEY=your_langsmith_api_key # For LangSmith tracing
```

### Run

The `src/agent/__init__.py` exposes the main `graph` object. To run the agent, you would typically have a main script that initializes and invokes this graph, possibly in a loop or driven by a system like FastAPI.

```bash
# Example (assuming you have a main.py that invokes the agent's graph)
python main.py
```

## 📖 Usage

The agent is designed to receive and process requests from a Redis stream named 'requests'. Here's a conceptual example of how to interact with it:

### Sending a Request to the Agent

You can push messages to the Redis stream that the agent listens to.

```python
import redis
import json

r = redis.Redis(host='localhost', port=6379, db=0)

request_data = {
    "task_id": "12345",
    "patient_id": "P001",
    "action": "schedule_appointment",
    "details": "Patient needs a cardiology appointment next week."
}

# Add the request to the Redis stream
r.xadd('requests', {'data': json.dumps(request_data)})
print("Request sent to Redis stream 'requests'")
```

### Agent Processing (Conceptual)

Once the agent receives the request from the Redis stream, its LangGraph will process it based on its defined nodes and transitions. The `responder` node might then decide to send a response to another Redis stream or update a database.

```python
# The agent, running in the background, would consume this message:
#
# from agent.graph import graph
#
# # Assuming the graph is invoked with the received message data
# result = graph.invoke({"request": request_data})
# print(result)
```

## 📚 Resources

- [LangGraph Documentation](https://langgraph.readthedocs.io/en/latest/) — Framework for building stateful, multi-actor applications with LLMs
- [Redis Streams Documentation](https://redis.io/docs/latest/develop/data-structures/streams/) — Guide to Redis stream data structure
- [Python Threading Documentation](https://docs.python.org/3/library/threading.html) — Official Python documentation on threading
- [LangChain Expression Language (LCEL) Config](https://python.langchain.com/docs/expression_language/config/) — Configuration options for LCEL runnables
- [Pytest Documentation](https://docs.pytest.org/en/latest/) — Python test framework documentation
- [AnyIO Documentation](https://anyio.readthedocs.io/en/stable/) — Asynchronous I/O for multiple backends
- [LangSmith Testing Documentation](https://docs.smith.langchain.com/tracing/testing/) — Information on testing with LangSmith

## 📄 License

MIT © [Your Name](https://github.com/yourusername)
