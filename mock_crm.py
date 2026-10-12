import random

from fastapi import FastAPI, HTTPException

app = FastAPI()


@app.get("/clientes/{cliente_id}")
def cliente(cliente_id: str):
    if random.random() < 0.3:
        raise HTTPException(status_code=random.choice([429, 500]))
    return {"id": cliente_id, "nombre": "Cliente demo", "plan": random.choice(["basico", "premium"])}
