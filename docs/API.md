# API (Draft)

## POST /v1/upload
- form-data: file
- response: doc_id

## POST /v1/index
- body: {doc_id}
- response: status

## POST /v1/query
- body: {query, top_k, filters}
- response: {answer, citations}

## POST /v1/chat
- body: {messages, tools, filters}
- response: {answer, citations}

## POST /v1/eval/run
- body: {dataset, framework}
- response: {run_id}
