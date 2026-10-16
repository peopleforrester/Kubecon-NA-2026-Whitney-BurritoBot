// ABOUTME: Audience phone page behaviour — sends prompts to /chat and lists the replies.
// ABOUTME: Replies render with textContent only; the 10/minute limit surfaces as a friendly 429 note.
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

  function failureText(status) {
    if (status === 429) {
      return "Whoa, this network has sent 10 prompts in the last minute. Give it a moment and try again.";
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
      const resp = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: prompt }),
      });
      if (!resp.ok) {
        turn.reply.textContent = failureText(resp.status);
        turn.reply.className = "reply error";
        return;
      }
      const body = await resp.json();
      const mode = MODE[body.target] || body.target;
      turn.who.textContent = "BurritBot · " + mode;
      turn.who.dataset.mode = mode;
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
