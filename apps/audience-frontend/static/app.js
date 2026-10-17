// ABOUTME: Audience phone page behaviour — sends prompts to /chat and lists the replies.
// ABOUTME: Sends a per-browser token for the /chat limit; replies render with textContent only.
"use strict";

(function () {
  const form = document.getElementById("prompt-form");
  const box = document.getElementById("prompt");
  const send = document.getElementById("send");
  const asks = document.querySelectorAll(".ask");
  const log = document.getElementById("log");

  // cast-net.sh flips the backend target; each reply says which bot answered.
  const MODE = {
    "burritbot-unguarded": "unguarded",
    "burritbot-guarded": "guarded",
  };

  // The /chat limit is per browser (question 157): a random token kept in
  // localStorage, so a reload keeps its budget. Where storage is blocked the
  // page sends none, and the server holds the phone to its address's budget.
  const TOKEN_KEY = "burritbot-audience-token";
  const TOKEN = (function () {
    try {
      let token = window.localStorage.getItem(TOKEN_KEY);
      if (!/^[0-9a-f]{32}$/.test(token || "")) {
        const bytes = new Uint8Array(16);
        window.crypto.getRandomValues(bytes);
        token = Array.from(bytes, function (b) {
          return b.toString(16).padStart(2, "0");
        }).join("");
        window.localStorage.setItem(TOKEN_KEY, token);
      }
      return token;
    } catch (err) {
      return null;
    }
  })();

  function addTurn(prompt) {
    const item = document.createElement("li");
    item.className = "turn";
    const you = document.createElement("p");
    you.className = "you";
    you.textContent = prompt;
    const who = document.createElement("p");
    who.className = "who";
    who.textContent = "BurritBot";
    const reply = document.createElement("p");
    reply.className = "reply pending";
    reply.textContent = "Thinking…";
    item.append(you, who, reply);
    log.prepend(item);
    return { who: who, reply: reply };
  }

  function labelMode(turn, target) {
    const mode = MODE[target] || target;
    turn.who.textContent = "BurritBot · " + mode;
    turn.who.dataset.mode = mode;
  }

  // The guardrails refuse a prompt or reply with a 403 that names the scanner
  // in blocked_by and says why in detail; main.py relays it with the target.
  // Any other 403 is an error like the rest.
  function refusalOf(body) {
    if (body && typeof body.blocked_by === "string" && typeof body.detail === "string") {
      return body;
    }
    return null;
  }

  // Act 2: a refusal is BurritBot sticking to burritos, so it reads as a reply.
  function showRefusal(turn, refusal) {
    labelMode(turn, refusal.target);
    turn.reply.textContent = refusal.detail;
    turn.reply.className = "reply refused";
  }

  function failureText(status, limit) {
    if (status === 429 && limit === "network") {
      return "Whoa, this Wi-Fi network has sent a lot of prompts in the last minute. Give it a moment, or switch to cellular.";
    }
    if (status === 429) {
      return "Whoa, that's a lot of prompts from this phone in the last minute. Give it a moment and try again.";
    }
    if (status === 422) {
      return "That prompt is empty or longer than 2000 characters.";
    }
    if (status === 502 || status === 503 || status === 504) {
      return "BurritBot is unreachable right now. Try again in a moment.";
    }
    return "Something went wrong (HTTP " + status + ").";
  }

  function setBusy(busy) {
    send.disabled = busy;
    asks.forEach(function (button) {
      button.disabled = busy;
    });
  }

  async function submit(prompt) {
    const turn = addTurn(prompt);
    setBusy(true);
    try {
      const headers = { "Content-Type": "application/json" };
      if (TOKEN) {
        headers["X-Audience-Token"] = TOKEN;
      }
      const resp = await fetch("/chat", {
        method: "POST",
        headers: headers,
        body: JSON.stringify({ prompt: prompt }),
      });
      if (!resp.ok) {
        let body = null;
        if (resp.status === 429 || resp.status === 403) {
          body = await resp.json().catch(function () {
            return null;
          });
        }
        const refusal = resp.status === 403 ? refusalOf(body) : null;
        if (refusal) {
          showRefusal(turn, refusal);
          return;
        }
        turn.reply.textContent = failureText(resp.status, body && body.limit);
        turn.reply.className = "reply error";
        return;
      }
      const body = await resp.json();
      labelMode(turn, body.target);
      turn.reply.textContent = body.reply;
      turn.reply.className = "reply";
    } catch (err) {
      turn.reply.textContent = "No connection. Check your Wi-Fi or cellular signal and try again.";
      turn.reply.className = "reply error";
    } finally {
      setBusy(false);
    }
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    const prompt = box.value.trim();
    if (!prompt) {
      return;
    }
    box.value = "";
    box.blur();
    submit(prompt);
  });

  asks.forEach(function (button) {
    button.addEventListener("click", function () {
      submit(button.dataset.prompt);
    });
  });
})();
