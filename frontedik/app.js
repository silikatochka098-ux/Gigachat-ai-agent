const state = {
  files: [],
  messages: [],
  theme: localStorage.getItem('energon-theme') || 'light',

  // Параметры текущего изделия
  parameters: null,

  // Текущий вопрос агента
  currentQuestion: null,

  // Можно ли уже рассчитывать
  calculationReady: false,
};


const $ = (selector) =>
  document.querySelector(selector);


const fileInput =
  $('#fileInput');

const dropzone =
  $('#dropzone');

const fileList =
  $('#fileList');

const chatWindow =
  $('#chatWindow');

const emptyChat =
  $('#emptyChat');

const chatSection =
  $('#chatSection');

const toast =
  $('#toast');


const API_BASE = '/api';


// ============================================================
// HTTP
// ============================================================

async function httpJson(
  url,
  options = {}
) {
  const response =
    await fetch(url, options);

  if (!response.ok) {

    let detail =
      'Ошибка API';

    try {
      detail =
        await response.text();
    } catch (e) {
      detail =
        response.statusText;
    }

    throw new Error(
      detail ||
      `HTTP ${response.status}`
    );
  }

  return response.json();
}


async function httpUpload(
  url,
  formData
) {
  const response =
    await fetch(url, {
      method: 'POST',
      body: formData,
    });

  if (!response.ok) {

    let detail =
      'Ошибка загрузки API';

    try {
      detail =
        await response.text();
    } catch (e) {
      detail =
        response.statusText;
    }

    throw new Error(
      detail ||
      `HTTP ${response.status}`
    );
  }

  return response.json();
}


// ============================================================
// API CLIENT
// ============================================================

const apiClient = {

  // ------------------------------------------
  // Анализ чертежа
  // ------------------------------------------

  async analyzeDrawing(
    file,
    description = ''
  ) {

    const formData =
      new FormData();

    formData.append(
      'file',
      file
    );

    formData.append(
      'description',
      description
    );

    return httpUpload(
      `${API_BASE}/analyze/drawing`,
      formData
    );
  },


  // ------------------------------------------
  // Уточнение
  // ------------------------------------------

  async clarify(
    question,
    answer,
    parameters
  ) {

    return httpJson(
      `${API_BASE}/clarify`,
      {
        method: 'POST',

        headers: {
          'Content-Type':
            'application/json',
        },

        body: JSON.stringify({
          question,
          answer,
          parameters,
        }),
      }
    );
  },


  // ------------------------------------------
  // Excel-калькулятор
  // ------------------------------------------

  async buildQuote(
    parameters
  ) {

    return httpJson(
      `${API_BASE}/calculator/quote`,
      {
        method: 'POST',

        headers: {
          'Content-Type':
            'application/json',
        },

        body: JSON.stringify(
          parameters
        ),
      }
    );
  },


  // ------------------------------------------
  // Старый endpoint GigaChat.
  // Оставляем на будущее.
  // ------------------------------------------

  async gigaChat(message) {

    return httpJson(
      `${API_BASE}/gigachat/chat`,
      {
        method: 'POST',

        headers: {
          'Content-Type':
            'application/json',
        },

        body: JSON.stringify({
          message,
        }),
      }
    );
  },
};


// ============================================================
// ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
// ============================================================

function now() {

  return new Intl.DateTimeFormat(
    'ru-RU',
    {
      hour: '2-digit',
      minute: '2-digit',
    }
  ).format(new Date());
}


function escapeHtml(value) {

  return String(
    value ?? ''
  ).replace(
    /[&<>'"]/g,

    (char) => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      "'": '&#039;',
      '"': '&quot;',
    }[char])
  );
}


function showToast(message) {

  if (!toast) return;

  toast.textContent =
    message;

  toast.classList.add(
    'is-visible'
  );

  window.clearTimeout(
    showToast.timer
  );

  showToast.timer =
    window.setTimeout(
      () =>
        toast.classList.remove(
          'is-visible'
        ),
      2800
    );
}


function formatSize(bytes) {

  return `${
    Math.max(
      1,
      Math.round(bytes / 1024)
    )
  } КБ`;
}


// ============================================================
// ФАЙЛЫ
// ============================================================

function renderFiles() {

  if (!fileList) return;

  fileList.innerHTML =
    state.files
      .map(
        (file, index) => `
          <div class="file-item">

            <span>
              ◫ ${escapeHtml(file.name)}

              <small>
                ${formatSize(file.size)}
              </small>
            </span>

            <button
              class="remove-file"
              data-index="${index}"
              type="button"
              aria-label="Удалить файл"
            >
              ×
            </button>

          </div>
        `
      )
      .join('');


  fileList
    .querySelectorAll(
      '.remove-file'
    )
    .forEach(
      (button) => {

        button.addEventListener(
          'click',
          () => {

            state.files.splice(
              Number(
                button.dataset.index
              ),
              1
            );

            renderFiles();
          }
        );
      }
    );
}


function addFiles(files) {

  const accepted =
    [...files].filter(
      (file) =>
        file.size <=
        25 * 1024 * 1024
    );


  if (
    accepted.length <
    files.length
  ) {

    showToast(
      'Файл больше допустимого размера 25 МБ'
    );
  }


  state.files = [
    ...state.files,
    ...accepted,
  ];


  renderFiles();
}


// ============================================================
// ЧАТ
// ============================================================

function addMessage(
  role,
  html,
  fileName = ''
) {

  state.messages.push({

    role,

    html,

    fileName,

    time: now(),
  });


  renderMessages();
}


function renderMessages() {

  if (
    !chatWindow ||
    !emptyChat
  ) {
    return;
  }


  emptyChat.hidden =
    state.messages.length > 0;


  chatWindow
    .querySelectorAll(
      '.message'
    )
    .forEach(
      (node) =>
        node.remove()
    );


  state.messages.forEach(
    (message) => {

      const node =
        document.createElement(
          'article'
        );


      node.className =
        `message ${message.role}`;


      node.innerHTML = `

        <div class="message-meta">

          ${
            message.role === 'user'
              ? 'Вы'
              : 'Energon AI'
          }

          · ${message.time}

        </div>


        ${message.html}


        ${
          message.fileName
            ? `
              <span class="file-pill">
                ◫ ${escapeHtml(
                  message.fileName
                )}
              </span>
            `
            : ''
        }

      `;


      chatWindow.appendChild(
        node
      );
    }
  );


  chatWindow.scrollTop =
    chatWindow.scrollHeight;
}


// ============================================================
// ПАРАМЕТРЫ
// ============================================================

function normalizeParameters(
  data
) {

  if (
    !data ||
    typeof data !== 'object'
  ) {

    return {

      material: null,

      thickness: null,

      dimensions: null,

      quantity: null,

      operations: [],

    };
  }


  const material =
    data['материал'] ??
    data.material ??
    null;


  const thickness =
    data['толщина_мм'] ??
    data.thickness ??
    data.thickness_mm ??
    null;


  const length =
    data['длина_мм'] ??
    data.length ??
    data.length_mm ??
    null;


  const width =
    data['ширина_мм'] ??
    data.width ??
    data.width_mm ??
    null;


  const quantity =
    data['количество'] ??
    data.quantity ??
    null;


  const operations =
    data['операции'] ??
    data.operations ??
    [];


  return {

    material,

    thickness,

    dimensions:
      length !== null ||
      width !== null
        ? `${length ?? '—'} × ${
            width ?? '—'
          } мм`
        : null,

    quantity,

    operations:
      Array.isArray(
        operations
      )
        ? operations
        : operations
          ? [operations]
          : [],

    raw: data,
  };
}


function displayValue(
  value,
  suffix = ''
) {

  if (
    value === null ||
    value === undefined ||
    value === '' ||
    (
      Array.isArray(value) &&
      value.length === 0
    )
  ) {

    return 'Не указано';
  }


  return (
    `${escapeHtml(value)}${suffix}`
  );
}


// ============================================================
// КАРТОЧКА ПАРАМЕТРОВ
// ============================================================

function parametersCard(
  data
) {

  const normalized =
    normalizeParameters(
      data
    );


  const operationsText =
    normalized.operations.length
      ? normalized.operations.join(
          ', '
        )
      : 'Не указано';


  return `

    <div class="parameters">


      <div class="parameter">

        <small>
          Материал
        </small>

        <strong>
          ${displayValue(
            normalized.material
          )}
        </strong>

      </div>


      <div class="parameter">

        <small>
          Толщина
        </small>

        <strong>

          ${displayValue(
            normalized.thickness,

            normalized.thickness !== null
              ? ' мм'
              : ''
          )}

        </strong>

      </div>


      <div class="parameter">

        <small>
          Габариты
        </small>

        <strong>
          ${displayValue(
            normalized.dimensions
          )}
        </strong>

      </div>


      <div class="parameter">

        <small>
          Количество
        </small>

        <strong>

          ${displayValue(
            normalized.quantity,

            normalized.quantity !== null
              ? ' шт.'
              : ''
          )}

        </strong>

      </div>


      <div class="parameter">

        <small>
          Операции
        </small>

        <strong>
          ${escapeHtml(
            operationsText
          )}
        </strong>

      </div>


    </div>

  `;
}


// ============================================================
// КНОПКА РАСЧЁТА
// ============================================================

function calculatorButton() {

  return `

    <div class="result-actions">

      <button
        class="small-button"
        type="button"
        id="calculateQuote"
      >
        🧮 Рассчитать стоимость
      </button>

    </div>

  `;
}


// ============================================================
// ПРИВЯЗКА КНОПКИ РАСЧЁТА
// ============================================================

function bindCalculatorButton() {

  const button =
    $('#calculateQuote');


  if (!button) return;


  button.addEventListener(
    'click',
    async () => {

      if (
        !state.parameters
      ) {

        showToast(
          'Нет параметров для расчёта'
        );

        return;
      }


      button.disabled = true;

      button.textContent =
        '🧮 Рассчитываю…';


      try {

        const result =
          await apiClient.buildQuote(
            state.parameters
          );


        if (
          result?.error
        ) {

          throw new Error(
            result.message ||
            result.error
          );
        }


        if (
          !result.download_url
        ) {

          throw new Error(
            'Калькулятор не вернул ссылку на КП.'
          );
        }


        const downloadUrl =
          result.download_url;


        button.outerHTML = `

          <a
            class="small-button"
            href="${escapeHtml(
              downloadUrl
            )}"
            download
          >
            ↓ Скачать готовое КП
          </a>

        `;


        showToast(
          'Готовое КП создано'
        );


      } catch (error) {

        button.disabled = false;

        button.textContent =
          '🧮 Рассчитать стоимость';


        showToast(
          error.message ||
          'Ошибка расчёта'
        );


        addMessage(
          'agent',

          `

            <div class="error-message">

              <strong>
                Не удалось рассчитать стоимость.
              </strong>

              <p>
                ${escapeHtml(
                  error.message ||
                  String(error)
                )}
              </p>

            </div>

          `
        );
      }
    }
  );
}


// ============================================================
// ОБРАБОТКА ПЕРВИЧНОЙ ЗАЯВКИ
// ============================================================

async function processFileRequest(
  text,
  file
) {

  addMessage(
    'user',

    escapeHtml(
      text ||
      'Прошу проанализировать прикреплённый чертёж.'
    ),

    file.name
  );


  addMessage(
    'agent',

    `

      <span class="typing">
        Агент анализирует заявку…
      </span>

    `
  );


  const typingMessage =
    state.messages[
      state.messages.length - 1
    ];


  try {

    // ------------------------------------------
    // Единственный запрос анализа
    // ------------------------------------------

    const result =
      await apiClient.analyzeDrawing(
        file,
        text || ''
      );


    if (
      result?.error
    ) {

      throw new Error(
        result.message ||
        result.error
      );
    }


    // ------------------------------------------
    // Сохраняем параметры
    // ------------------------------------------

    state.parameters =
      result.parameters || {};


    state.currentQuestion =
      result.question || null;


    state.calculationReady =
      result.status === 'complete';


    // ------------------------------------------
    // Формируем ответ
    // ------------------------------------------

    let resultHtml = `

      <p>

        <strong>
          Чертёж проанализирован.
        </strong>

      </p>


      ${parametersCard(
        state.parameters
      )}

    `;


    // ------------------------------------------
    // Если чего-то не хватает
    // ------------------------------------------

    if (
      result.status !==
      'complete'
    ) {

      resultHtml += `

        <div class="clarification">

          <strong>
            Нужно уточнить:
          </strong>


          <p>
            ${
              escapeHtml(
                result.question ||
                'Укажите недостающие параметры.'
              )
            }
          </p>

        </div>

      `;

    } else {

      resultHtml += `

        <div class="clarification">

          <strong>
            ✅ Основные параметры получены.
          </strong>

          <p>
            Можно перейти к расчёту стоимости.
          </p>

        </div>


        ${calculatorButton()}

      `;
    }


    typingMessage.html =
      resultHtml;


    renderMessages();


    if (
      result.status ===
      'complete'
    ) {

      bindCalculatorButton();
    }


  } catch (error) {

    typingMessage.html = `

      <div class="error-message">

        <strong>
          Не удалось обработать заявку.
        </strong>

        <p>
          ${escapeHtml(
            error.message ||
            String(error)
          )}
        </p>

      </div>

    `;


    renderMessages();
  }
}


// ============================================================
// ОБРАБОТКА ОТВЕТА ПОЛЬЗОВАТЕЛЯ
// ============================================================

async function processClarification(
  text
) {

  if (
    !state.parameters ||
    !state.currentQuestion
  ) {

    addMessage(
      'user',
      escapeHtml(text)
    );


    addMessage(
      'agent',

      `

        <p>
          Сначала загрузите чертёж,
          чтобы начать анализ.
        </p>

      `
    );


    return;
  }


  addMessage(
    'user',
    escapeHtml(text)
  );


  addMessage(
    'agent',

    `

      <span class="typing">
        Проверяю ответ…
      </span>

    `
  );


  const typingMessage =
    state.messages[
      state.messages.length - 1
    ];


  try {

    const result =
      await apiClient.clarify(

        state.currentQuestion,

        text,

        state.parameters
      );


    if (
      result?.error
    ) {

      throw new Error(
        result.message ||
        result.error
      );
    }


    // ------------------------------------------
    // Обновляем параметры
    // ------------------------------------------

    state.parameters =
      result.parameters ||
      state.parameters;


    state.currentQuestion =
      result.question ||
      null;


    state.calculationReady =
      result.status ===
      'complete';


    // ------------------------------------------
    // Ответ неоднозначный
    // ------------------------------------------

    if (
      result.status ===
      'needs_confirmation'
    ) {

      typingMessage.html = `

        <div class="clarification">

          <strong>
            ⚠️ Нужно подтвердить значение
          </strong>

          <p>
            ${escapeHtml(
              result.question
            )}
          </p>

        </div>

      `;


      renderMessages();

      return;
    }


    // ------------------------------------------
    // Показываем обновлённые параметры
    // ------------------------------------------

    let html = `

      <p>

        <strong>
          Параметры обновлены.
        </strong>

      </p>


      ${parametersCard(
        state.parameters
      )}

    `;


    // ------------------------------------------
    // Остались вопросы
    // ------------------------------------------

    if (
      result.status !==
      'complete'
    ) {

      html += `

        <div class="clarification">

          <strong>
            Следующий вопрос:
          </strong>

          <p>
            ${escapeHtml(
              result.question ||
              'Уточните следующий параметр.'
            )}
          </p>

        </div>

      `;

    } else {

      html += `

        <div class="clarification">

          <strong>
            ✅ Все основные параметры получены.
          </strong>

          <p>
            Теперь можно рассчитать стоимость.
          </p>

        </div>


        ${calculatorButton()}

      `;
    }


    typingMessage.html =
      html;


    renderMessages();


    if (
      result.status ===
      'complete'
    ) {

      bindCalculatorButton();
    }


  } catch (error) {

    typingMessage.html = `

      <div class="error-message">

        <strong>
          Не удалось обработать ответ.
        </strong>

        <p>
          ${escapeHtml(
            error.message ||
            String(error)
          )}
        </p>

      </div>

    `;


    renderMessages();
  }
}


// ============================================================
// ГЛАВНАЯ ФУНКЦИЯ
// ============================================================

async function processRequest(
  text,
  files
) {

  const file =
    files[0];


  // ------------------------------------------
  // Есть новый файл
  // ------------------------------------------

  if (file) {

    await processFileRequest(
      text,
      file
    );

    return;
  }


  // ------------------------------------------
  // Нет файла → это ответ
  // на вопрос агента
  // ------------------------------------------

  await processClarification(
    text
  );
}


// ============================================================
// ПРОКРУТКА К ЧАТУ
// ============================================================

function goToChatSmoothly() {

  if (!chatSection) return;

  chatSection.scrollIntoView({
    behavior: 'smooth',
    block: 'start',
  });
}


// ============================================================
// ЗАГРУЗКА ФАЙЛА
// ============================================================

fileInput?.addEventListener(
  'change',
  (event) => {

    addFiles(
      event.target.files
    );
  }
);


// ============================================================
// DRAG & DROP
// ============================================================

[
  'dragenter',
  'dragover'
].forEach(
  (eventName) => {

    dropzone?.addEventListener(
      eventName,
      (event) => {

        event.preventDefault();

        dropzone.classList.add(
          'is-dragging'
        );
      }
    );
  }
);


[
  'dragleave',
  'drop'
].forEach(
  (eventName) => {

    dropzone?.addEventListener(
      eventName,
      (event) => {

        event.preventDefault();

        dropzone.classList.remove(
          'is-dragging'
        );
      }
    );
  }
);


dropzone?.addEventListener(
  'drop',
  (event) => {

    addFiles(
      event.dataTransfer.files
    );
  }
);


// ============================================================
// ФОРМА ПЕРВИЧНОЙ ЗАЯВКИ
// ============================================================

$('#requestForm')?.addEventListener(
  'submit',
  async (event) => {

    event.preventDefault();


    const text =
      $('#requestText')
        ?.value
        .trim() || '';


    if (
      !text &&
      !state.files.length
    ) {

      showToast(
        'Добавьте описание или загрузите файл'
      );

      return;
    }


    await processRequest(
      text,
      state.files
    );


    if (
      $('#requestText')
    ) {

      $('#requestText').value =
        '';
    }


    goToChatSmoothly();
  }
);


// ============================================================
// ФОРМА ЧАТА
// ============================================================

$('#chatForm')?.addEventListener(
  'submit',
  async (event) => {

    event.preventDefault();


    const input =
      $('#chatInput');


    const text =
      input?.value.trim() ||
      '';


    if (!text) return;


    input.value =
      '';


    await processRequest(
      text,
      []
    );


    goToChatSmoothly();
  }
);


// ============================================================
// ПРИКРЕПЛЕНИЕ ФАЙЛА ИЗ ЧАТА
// ============================================================

$('#chatAttach')?.addEventListener(
  'click',
  () => {

    fileInput?.click();

  }
);


// ============================================================
// ТЕМА
// ============================================================

$('#themeToggle')?.addEventListener(
  'click',
  () => {

    state.theme =
      state.theme === 'dark'
        ? 'light'
        : 'dark';


    document.documentElement.dataset.theme =
      state.theme;


    localStorage.setItem(
      'energon-theme',
      state.theme
    );
  }
);


document.documentElement.dataset.theme =
  state.theme;