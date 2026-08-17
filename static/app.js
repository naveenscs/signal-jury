const q = document.getElementById("q");
const go = document.getElementById("go");
const status = document.getElementById("status");
const briefEl = document.getElementById("brief");
const votesEl = document.getElementById("votes");

const samples = [
  "Will multi-agent systems become mainstream by 2027?",
  "Will Claude system prompts be widely adopted?",
  "Will software engineering fundamentals gain more industry emphasis?",
];

if (!q.value) q.value = samples[Math.floor(Math.random() * samples.length)];

go.addEventListener("click", async () => {
  const question = q.value.trim();
  if (question.length < 3) {
    status.textContent = "Enter a longer question.";
    return;
  }

  go.disabled = true;
  status.textContent = "Querying live miners…";
  briefEl.classList.add("hidden");
  votesEl.innerHTML = "";

  try {
    const res = await fetch("/api/deliberate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.statusText);

    const b = data.brief;
    briefEl.classList.remove("hidden");
    briefEl.innerHTML = `
      <h2 class="brief-title">Jury brief</h2>
      <p class="summary">${escapeHtml(b.summary)}</p>
      <p class="meta">
        Consensus: <strong>${escapeHtml(b.consensus)}</strong>
        · ${b.miners_succeeded}/${b.miners_queried} miners succeeded
        · mocks: false
      </p>
      <p class="meta">${escapeHtml(b.telegraph_note)}</p>
    `;

    votesEl.innerHTML = (data.votes || [])
      .map((v) => {
        const ok = v.status === "success";
        return `
        <article class="card">
          <h3>
            ${escapeHtml(v.name || "miner")}
            <span class="badge ${ok ? "ok" : "err"}">${ok ? "success" : "error"}</span>
          </h3>
          <p class="meta">${escapeHtml(v.base_url || "")}${v.path_used ? " · " + escapeHtml(v.path_used) : ""} · ${v.elapsed_ms || 0}ms</p>
          ${ok ? `<p class="out">${escapeHtml(v.output || "")}</p>` : `<p class="err">${escapeHtml(v.error || "failed")}</p>`}
        </article>`;
      })
      .join("");

    status.textContent = "Done.";
  } catch (err) {
    status.textContent = String(err.message || err);
  } finally {
    go.disabled = false;
  }
});

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}
