/* Shared-element FLIP adapted from justtemp/moxen-despliegue. */
function muelle(k, c) {
  const dt = 1 / 240;
  const points = [0];
  let progress = 0;
  let velocity = 0;
  let step = 0;
  do {
    velocity += (k * (1 - progress) - c * velocity) * dt;
    progress += velocity * dt;
    step++;
    points.push(Number(progress.toFixed(5)));
  } while (step < 720 && (Math.abs(1 - progress) > 0.0015 || Math.abs(velocity) > 0.02));
  points[step] = 1;
  return {
    duration: step * dt * 1000,
    easing: CSS.supports("animation-timing-function", "linear(0, 1)")
      ? `linear(${points.join(",")})` : "cubic-bezier(.22,1,.36,1)",
  };
}

function openAgentFlight(dialog, trigger) {
  if (dialog.open) return;
  const card = trigger.closest(".agent-directory-card");
  const surface = dialog.querySelector(".agent-flight-surface");
  const closeButton = dialog.querySelector("[data-flight-close]");
  const pieces = [...card.querySelectorAll("[data-pieza]")];
  const origins = pieces.map(piece => piece.getBoundingClientRect());
  const cardRect = card.getBoundingClientRect();
  const placeholders = pieces.map(() => document.createComment("moxen"));
  const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches ||
    document.body.classList.contains("reduce-motion-forced");
  const curve = muelle(180, 24);
  const expanded = "inset(0px 0px 0px 0px round 3px)";
  const collapsed = box => {
    const frame = surface.getBoundingClientRect();
    const edges = [box.top - frame.top, frame.right - box.right,
      frame.bottom - box.bottom, box.left - frame.left].map(value => `${Math.max(0, value)}px`);
    return `inset(${edges.join(" ")} round 3px)`;
  };

  dialog.showModal();
  dialog.scrollTop = 0;
  pieces.forEach((piece, index) => {
    piece.before(placeholders[index]);
    dialog.querySelector(`[data-hueco="${piece.dataset.pieza}"]`).replaceChildren(piece);
  });
  trigger.setAttribute("aria-expanded", "true");

  const fly = (piece, from, to, opening) => {
    const reference = opening ? to : from;
    if (!reference.width || !reference.height) return null;
    const delta = opening ? from : to;
    const transform = `translate(${delta.left - reference.left}px,${delta.top - reference.top}px) scale(${delta.width / reference.width},${delta.height / reference.height})`;
    const frames = opening ? [{ transform }, { transform: "none" }] : [{ transform: "none" }, { transform }];
    return piece.animate(frames, { ...curve, fill: opening ? "none" : "forwards" });
  };
  const entry = reduced() ? [] : [
    surface.animate([{ clipPath: collapsed(cardRect) }, { clipPath: expanded }], curve),
    ...pieces.map((piece, index) => fly(piece, origins[index], piece.getBoundingClientRect(), true)).filter(Boolean),
  ];
  let closing = false;
  const restore = () => {
    pieces.forEach((piece, index) => placeholders[index].replaceWith(piece));
    trigger.setAttribute("aria-expanded", "false");
    dialog.removeEventListener("cancel", dismiss);
    closeButton.removeEventListener("click", dismiss);
    dialog.close();
    trigger.focus({ preventScroll: true });
  };
  async function dismiss(event) {
    event.preventDefault();
    if (closing) return;
    closing = true;
    entry.forEach(animation => animation.cancel());
    if (!reduced() && card.isConnected) {
      const from = pieces.map(piece => piece.getBoundingClientRect());
      // Measure the restored card, then temporarily return pieces to the top layer for the flight.
      pieces.forEach((piece, index) => placeholders[index].before(piece));
      const to = pieces.map(piece => piece.getBoundingClientRect());
      const clip = collapsed(card.getBoundingClientRect());
      pieces.forEach(piece => dialog.querySelector(`[data-hueco="${piece.dataset.pieza}"]`).append(piece));
      const animations = [
        surface.animate([{ clipPath: expanded }, { clipPath: clip }], { ...curve, fill: "forwards" }),
        ...pieces.map((piece, index) => fly(piece, from[index], to[index], false)).filter(Boolean),
      ];
      await Promise.allSettled(animations.map(animation => animation.finished));
      animations.forEach(animation => animation.cancel());
    }
    restore();
  }
  closeButton.addEventListener("click", dismiss);
  dialog.addEventListener("cancel", dismiss);
}
