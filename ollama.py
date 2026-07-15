import json
import requests

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "llama3.2:3b"


def evaluate_trade_with_llm(condition_type, current_price, history_candles):
    """
    Sends breakout context to llama3.2:3b using a hyper-concise prompt optimized for 3B models.
    """
    global STOCK_NAME

    print(f"🤖 Contacting Ollama ({OLLAMA_MODEL}) AI Evaluator for {STOCK_NAME}...")

    # Compact context payload
    payload = {
        "ticker": STOCK_NAME,
        "signal": condition_type,
        "price": current_price,
        "candles_1m": history_candles[-15:] if len(history_candles) > 15 else history_candles # Trimmed to 15 candles to save context tokens
    }

    # Hyper-concise system prompt designed for a 3B model
    system_prompt = (
        "You are a conservative trading risk manager. "
        "Analyze the candles. Approve only clean breakouts with strong trend/momentum. "
        "Reject sideways, low-volume, or choppy markets. "
        "Output ONLY the required JSON schema. No explanation, no conversational text."
    )

    # Simplified user prompt
    prompt = f"Evaluate:\n{json.dumps(payload)}"

    # Strict JSON schema to force structure without needing prompt instructions
    json_schema = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["BUY", "SELL"]},
            "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
            "avoid_trade": {"type": "boolean"},
            "reason": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["action", "confidence", "avoid_trade", "reason"]
    }

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "stream": False,
                "format": json_schema,
                "options": {
                    "temperature": 0.0,  # 0.0 forces the model to be completely deterministic
                    "top_p": 0.9
                }
            },
            timeout=15  # 3B models with short prompts should respond within 1-2 seconds locally
        )

        response.raise_for_status()
        result = response.json()
        raw_response_text = result["message"]["content"].strip()
        
        data = json.loads(raw_response_text)
        print("💡 Ollama Evaluation complete.")
        return data

    except Exception as e:
        print(f"❌ Ollama Error: {e}")
        return {
            "action": condition_type,
            "confidence": 0,
            "avoid_trade": True,
            "reason": [f"Ollama execution error: {str(e)}"]
        }