/* app.js — Agente Ferroviario CNRT frontend logic */

'use strict';

// ──────────────────────────────────────────────────────────────
// Constants
// ──────────────────────────────────────────────────────────────
const HISTORIAL_KEY = 'historial';
const HISTORIAL_MAX = 10;
const HISTORIAL_DISPLAY = 5;

// ──────────────────────────────────────────────────────────────
// Entry point
// ──────────────────────────────────────────────────────────────
function init() {
  // Parallel initial fetches
  fetchEjemplos();
  fetchCobertura();

  // Wire up submit button
  document.getElementById('btn-consultar').addEventListener('click', () => {
    const pregunta = document.getElementById('input-pregunta').value.trim();
    if (pregunta) submitPregunta(pregunta);
  });

  // Wire up Enter key on input
  document.getElementById('input-pregunta').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      const btn = document.getElementById('btn-consultar');
      if (btn.disabled) return;
      const pregunta = document.getElementById('input-pregunta').value.trim();
      if (pregunta) submitPregunta(pregunta);
    }
  });

  // Render existing history chips on load (sessionStorage survives only until tab close)
  renderHistorialChips();
}

// ──────────────────────────────────────────────────────────────
// API: load example chips
// ──────────────────────────────────────────────────────────────
async function fetchEjemplos() {
  try {
    const res = await fetch('/api/ejemplos');
    if (!res.ok) return;
    const ejemplos = await res.json();
    const container = document.getElementById('chips-ejemplos');
    container.innerHTML = '';
    ejemplos.forEach((texto) => {
      const chip = buildChip(texto, 'example');
      chip.addEventListener('click', () => {
        document.getElementById('input-pregunta').value = texto;
        document.getElementById('input-pregunta').focus();
      });
      container.appendChild(chip);
    });
  } catch (_) {
    // Silently ignore — chips are a nice-to-have
  }
}

// ──────────────────────────────────────────────────────────────
// API: load coverage for footer
// ──────────────────────────────────────────────────────────────
async function fetchCobertura() {
  try {
    const res = await fetch('/api/cobertura');
    if (!res.ok) {
      document.getElementById('footer-cobertura').textContent = 'Cobertura de datos no disponible.';
      return;
    }
    const data = await res.json();
    const footer = document.getElementById('footer-cobertura');
    const rango = data.rango_general || {};
    let text = '';
    if (rango.desde && rango.hasta) {
      text = `Datos disponibles: ${rango.desde} — ${rango.hasta}.`;
    }
    const especiales = data.casos_especiales || [];
    especiales.forEach((caso) => {
      if (caso.linea && caso.nota) {
        text += ` ${caso.linea}: ${caso.nota}.`;
      }
    });
    footer.textContent = text || 'Cobertura de datos no disponible.';
  } catch (_) {
    document.getElementById('footer-cobertura').textContent = 'Cobertura de datos no disponible.';
  }
}

// ──────────────────────────────────────────────────────────────
// Core: submit a question
// ──────────────────────────────────────────────────────────────
async function submitPregunta(pregunta) {
  setLoading(true);

  try {
    const res = await fetch('/api/preguntar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pregunta }),
    });

    if (res.status === 429) {
      const data = await res.json().catch(() => ({}));
      showToast(data.detail || 'Demasiadas consultas. Esperá un minuto.');
      return;
    }

    if (!res.ok) {
      renderError('Error al consultar el servidor. Intentá de nuevo.');
      return;
    }

    const respuesta = await res.json();
    renderRespuesta(respuesta);
    updateHistorial(pregunta, respuesta);
  } catch (_) {
    renderError('No se pudo conectar con el servidor. Verificá tu conexión.');
  } finally {
    setLoading(false);
  }
}

// ──────────────────────────────────────────────────────────────
// Render: dispatch by tipo
// ──────────────────────────────────────────────────────────────
function renderRespuesta(respuesta) {
  const tipo = respuesta.tipo || 'error';
  const textoNl = respuesta.texto_nl || '';
  const advertencias = respuesta.advertencias || [];
  const metadata = respuesta.metadata || {};
  const intent = respuesta.intent || {};
  const fuente_nl = metadata.fuente_nl || '';
  const intentFallback = metadata.intent_fallback === true;

  renderProcedencia(intent, fuente_nl, intentFallback);

  // Render advertencias
  renderAdvertencias(advertencias);

  // Render card by tipo
  switch (tipo) {
    case 'dato':
      renderDato(respuesta.dato || {}, textoNl, advertencias, fuente_nl);
      break;
    case 'comparacion':
      renderComparacion(respuesta.comparacion || {}, textoNl, advertencias, fuente_nl);
      break;
    case 'ood':
    case 'sin_datos':
      renderSinDatos(textoNl, respuesta.sugerencias || [], advertencias);
      break;
    case 'error':
    default:
      renderError(textoNl || 'Ocurrió un error inesperado.');
      break;
  }

  // Render technical detail
  renderDetalleTecnico(respuesta.intent || {}, respuesta.metadata || {});

  // Show response area
  document.getElementById('response-area').classList.remove('hidden');
}

// ──────────────────────────────────────────────────────────────
// Render: tipo=dato
// ──────────────────────────────────────────────────────────────
function renderDato(dato, textoNl, advertencias, fuente_nl) {
  const card = document.getElementById('response-card');

  const valor = dato.valor != null ? formatNumber(dato.valor) : '—';
  const unidad = dato.unidad || '';
  const etiqueta = dato.etiqueta_humana || dato.metrica || '';

  card.innerHTML = `
    <div class="flex flex-col gap-3">
      ${etiqueta ? `<p class="text-xs font-semibold text-gray-400 uppercase tracking-wider">${escapeHtml(etiqueta)}</p>` : ''}
      <div class="flex items-baseline gap-2">
        <span class="text-4xl font-bold text-white">${escapeHtml(valor)}</span>
        ${unidad ? `<span class="text-lg text-gray-400">${escapeHtml(formatUnidad(unidad))}</span>` : ''}
      </div>
      ${textoNl ? `<p class="text-gray-300 text-sm leading-relaxed">${escapeHtml(textoNl)}</p>` : ''}
    </div>
  `;
}

// ──────────────────────────────────────────────────────────────
// Render: tipo=comparacion
// ──────────────────────────────────────────────────────────────
function renderComparacion(comp, textoNl, advertencias, fuente_nl) {
  const card = document.getElementById('response-card');

  // Use ranking order if present, otherwise use items order
  let items = comp.items || [];
  const ranking = comp.ranking || [];
  if (ranking.length > 0 && items.length > 0) {
    const byLabel = Object.fromEntries(items.map((it) => [it.etiqueta, it]));
    const ordered = ranking.map((lbl) => byLabel[lbl]).filter(Boolean);
    // Append any items not in ranking
    const inRanking = new Set(ranking);
    items.forEach((it) => { if (!inRanking.has(it.etiqueta)) ordered.push(it); });
    items = ordered;
  }

  const maxVal = items.reduce((m, it) => Math.max(m, Math.abs(it.valor || 0)), 1);

  const rowsHtml = items.map((it, idx) => {
    const pct = Math.round((Math.abs(it.valor || 0) / maxVal) * 100);
    const unidad = it.unidad || comp.unidad || '';
    return `
      <div class="flex flex-col gap-1">
        <div class="flex justify-between items-center text-sm">
          <span class="text-gray-200 font-medium">
            <span class="text-gray-500 mr-1">${idx + 1}.</span>${escapeHtml(it.etiqueta || '—')}
          </span>
          <span class="text-white font-semibold ml-2 whitespace-nowrap">
            ${escapeHtml(formatNumber(it.valor))}${unidad ? ' <span class="text-gray-400 font-normal text-xs">' + escapeHtml(formatUnidad(unidad)) + '</span>' : ''}
          </span>
        </div>
        <div class="w-full bg-gray-700 rounded-full h-1.5">
          <div class="bg-blue-500 h-1.5 rounded-full" style="width: ${pct}%"></div>
        </div>
      </div>
    `;
  }).join('');

  card.innerHTML = `
    <div class="flex flex-col gap-4">
      <div class="flex flex-col gap-3">
        ${rowsHtml || '<p class="text-gray-400 text-sm">Sin datos para mostrar.</p>'}
      </div>
      ${textoNl ? `<p class="text-gray-300 text-sm leading-relaxed border-t border-gray-700 pt-3">${escapeHtml(textoNl)}</p>` : ''}
    </div>
  `;
}

// ──────────────────────────────────────────────────────────────
// Render: tipo=ood / sin_datos
// ──────────────────────────────────────────────────────────────
function renderSinDatos(textoNl, sugerencias, advertencias) {
  const card = document.getElementById('response-card');

  const sugsHtml = sugerencias.map((sug) => {
    const chip = buildChip(sug, 'suggestion');
    chip.dataset.sug = sug;
    return chip.outerHTML;
  }).join('');

  card.innerHTML = `
    <div class="flex flex-col gap-4">
      <div class="flex items-start gap-3">
        <span class="text-2xl">&#128269;</span>
        <p class="text-gray-300 text-sm leading-relaxed">${escapeHtml(textoNl || 'No encontré datos para esa consulta.')}</p>
      </div>
      ${sugerencias.length > 0 ? `
        <div>
          <p class="text-xs text-gray-500 mb-2">Podés probar con:</p>
          <div class="flex flex-wrap gap-2" id="suggestion-chips">${sugsHtml}</div>
        </div>
      ` : ''}
    </div>
  `;

  // Wire suggestion chips to auto-submit
  if (sugerencias.length > 0) {
    card.querySelectorAll('[data-sug]').forEach((el) => {
      el.addEventListener('click', () => {
        const btn = document.getElementById('btn-consultar');
        if (btn.disabled) return;
        const sug = el.dataset.sug;
        document.getElementById('input-pregunta').value = sug;
        submitPregunta(sug);
      });
    });
  }
}

// ──────────────────────────────────────────────────────────────
// Render: tipo=error
// ──────────────────────────────────────────────────────────────
function renderError(textoNl) {
  const card = document.getElementById('response-card');
  card.innerHTML = `
    <div class="flex items-start gap-3">
      <span class="text-2xl">&#9888;&#65039;</span>
      <p class="text-red-300 text-sm leading-relaxed">${escapeHtml(textoNl || 'Ocurrió un error inesperado. Intentá de nuevo.')}</p>
    </div>
  `;
  document.getElementById('response-area').classList.remove('hidden');
  document.getElementById('procedencia').classList.add('hidden');
  renderAdvertencias([]);
  renderDetalleTecnico({}, {});
}

// ──────────────────────────────────────────────────────────────
// Render: provenance lines (intent + NL source)
// ──────────────────────────────────────────────────────────────
function renderProcedencia(intent, fuente_nl, intentFallback) {
  const container = document.getElementById('procedencia');
  const intentEl = document.getElementById('proc-intent');
  const nlEl = document.getElementById('proc-nl');

  const origen = intent.origen || 'reglas';
  const intentLabel = (origen === 'reglas' || intentFallback) ? 'Plantilla' : 'LLM';
  const nlLabel = fuente_nl === 'groq' ? 'LLM' : 'Plantilla';

  intentEl.textContent = intentLabel;
  nlEl.textContent = nlLabel;
  container.classList.remove('hidden');
}

// ──────────────────────────────────────────────────────────────
// Render: advertencias banners
// ──────────────────────────────────────────────────────────────
function renderAdvertencias(advertencias) {
  const area = document.getElementById('advertencias-area');
  area.innerHTML = '';
  (advertencias || []).forEach((adv) => {
    const el = document.createElement('div');
    el.className = 'bg-orange-900 border border-orange-600 text-orange-200 text-sm px-4 py-3 rounded-lg';
    el.textContent = adv;
    area.appendChild(el);
  });
}

// ──────────────────────────────────────────────────────────────
// Render: collapsible technical detail
// ──────────────────────────────────────────────────────────────
function renderDetalleTecnico(intent, metadata) {
  const content = document.getElementById('detalle-content');

  const rows = [];

  if (intent.metrica) rows.push(['Métrica', intent.metrica]);
  if (intent.tabla) rows.push(['Tabla', intent.tabla]);
  if (intent.granularidad) rows.push(['Granularidad', intent.granularidad]);
  if (intent.confianza != null) rows.push(['Confianza', (intent.confianza * 100).toFixed(0) + '%']);
  if (intent.origen) rows.push(['Origen intent', intent.origen]);

  if (intent.filtros_linea && intent.filtros_linea.length > 0) {
    rows.push(['Filtros línea', intent.filtros_linea.join(', ')]);
  }

  if (intent.rango_temporal) {
    const rt = intent.rango_temporal;
    const desde = rt.desde || rt.year_desde || '';
    const hasta = rt.hasta || rt.year_hasta || '';
    if (desde || hasta) {
      rows.push(['Rango temporal', [desde, hasta].filter(Boolean).join(' → ')]);
    }
  }

  if (metadata.fuente_nl) rows.push(['Fuente NL', metadata.fuente_nl]);
  if (metadata.tiempo_ms != null) rows.push(['Tiempo', metadata.tiempo_ms.toFixed(0) + ' ms']);
  if (metadata.cobertura_desde && metadata.cobertura_hasta) {
    rows.push(['Cobertura tabla', `${metadata.cobertura_desde} — ${metadata.cobertura_hasta}`]);
  }

  if (rows.length === 0) {
    content.innerHTML = '<p class="text-gray-600">Sin información de detalle.</p>';
    return;
  }

  content.innerHTML = rows.map(([label, val]) => `
    <div class="flex gap-2">
      <span class="text-gray-500 min-w-[110px]">${escapeHtml(label)}:</span>
      <span class="text-gray-300">${escapeHtml(String(val))}</span>
    </div>
  `).join('');
}

// ──────────────────────────────────────────────────────────────
// Session history
// ──────────────────────────────────────────────────────────────
function updateHistorial(pregunta, respuesta) {
  let historial = loadHistorial();
  // Prepend newest
  historial.unshift({ pregunta, respuesta });
  // Trim to max
  if (historial.length > HISTORIAL_MAX) historial = historial.slice(0, HISTORIAL_MAX);
  try {
    sessionStorage.setItem(HISTORIAL_KEY, JSON.stringify(historial));
  } catch (_) {
    // Storage full or unavailable
  }
  renderHistorialChips();
}

function loadHistorial() {
  try {
    const raw = sessionStorage.getItem(HISTORIAL_KEY);
    if (!raw) return [];
    return JSON.parse(raw);
  } catch (_) {
    return [];
  }
}

function renderHistorialChips() {
  const historial = loadHistorial();
  const area = document.getElementById('historial-area');
  const container = document.getElementById('historial-chips');

  if (historial.length === 0) {
    area.classList.add('hidden');
    return;
  }

  area.classList.remove('hidden');
  container.innerHTML = '';

  // Show last HISTORIAL_DISPLAY entries (they are newest-first already)
  historial.slice(0, HISTORIAL_DISPLAY).forEach((entry) => {
    const chip = buildChip(entry.pregunta, 'history');
    chip.addEventListener('click', () => {
      const btn = document.getElementById('btn-consultar');
      if (btn.disabled) return;
      document.getElementById('input-pregunta').value = entry.pregunta;
      submitPregunta(entry.pregunta);
    });
    container.appendChild(chip);
  });
}

// ──────────────────────────────────────────────────────────────
// Toast notification
// ──────────────────────────────────────────────────────────────
function showToast(msg) {
  const toast = document.getElementById('toast');
  toast.textContent = msg;
  toast.classList.remove('hidden');
  toast.style.opacity = '1';
  clearTimeout(toast._timeout);
  toast._timeout = setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.classList.add('hidden'), 300);
  }, 4000);
}

// ──────────────────────────────────────────────────────────────
// Loading state
// ──────────────────────────────────────────────────────────────
function setLoading(isLoading) {
  const btn = document.getElementById('btn-consultar');
  const btnText = document.getElementById('btn-text');
  const spinner = document.getElementById('btn-spinner');

  btn.disabled = isLoading;
  btnText.textContent = isLoading ? 'Consultando...' : 'Consultar';
  spinner.classList.toggle('hidden', !isLoading);
}

// ──────────────────────────────────────────────────────────────
// Helpers
// ──────────────────────────────────────────────────────────────
function buildChip(text, variant) {
  const el = document.createElement('button');
  el.type = 'button';

  if (variant === 'history') {
    el.className = 'chip text-xs px-3 py-2 rounded-lg border cursor-pointer select-none text-left w-full ' +
      'bg-gray-700 border-gray-600 text-gray-300 hover:bg-gray-600 hover:text-white transition';
  } else {
    el.className = 'chip text-xs px-3 py-1.5 rounded-full border cursor-pointer select-none max-w-xs truncate overflow-hidden ' +
      (variant === 'suggestion'
        ? 'bg-blue-900 border-blue-700 text-blue-200 hover:bg-blue-800 hover:text-white'
        : 'bg-gray-800 border-gray-600 text-gray-300 hover:bg-gray-700 hover:text-white');
  }

  el.textContent = text;
  return el;
}

function formatUnidad(u) {
  return /^\d[\d,.]*\s*[–—-]\s*\d[\d,.]*$/.test(u.trim()) ? `(${u})` : u;
}

function formatNumber(val) {
  if (val == null) return '—';
  const num = Number(val);
  if (isNaN(num)) return String(val);
  return num.toLocaleString('es-AR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// ──────────────────────────────────────────────────────────────
// Bootstrap
// ──────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', init);
