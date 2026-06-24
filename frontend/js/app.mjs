import {
  addFontFromFile,
  formatText,
  addPaperFromFile
} from './utils/helpers.mjs';
import {
  generateImages,
  downloadAsPDF,
  downloadAsZIP,
  deleteAll,
  moveLeft,
  moveRight
} from './generate-images.mjs';

window.downloadAsZIP = downloadAsZIP;
import { setInkColor, toggleDrawCanvas } from './utils/draw.mjs';

/**
 *
 * Hi there! This is the entry file of the tool and deals with adding event listeners
 * and some other functions.
 *
 * To contribute, you can follow the imports above and make changes in the file
 * related to the issue you've choosen.
 *
 * If you have any questions related to code, you can drop them in my Twitter DM @saurabhcodes
 * or in my email at saurabhdaware99@gmail.com
 *
 * Thanks! and Happy coding 🌻
 *
 */

const pageEl = document.querySelector('.page-a');

const setTextareaStyle = (attrib, v) => (pageEl.style[attrib] = v);

/**
 * Add event listeners here, they will be automatically mapped with addEventListener later
 */
const EVENT_MAP = {
  '#generate-image-form': {
    on: 'submit',
    action: (e) => {
      e.preventDefault();
      generateImages();
    }
  },
  '#handwriting-font': {
    on: 'change',
    action: (e) =>
      document.body.style.setProperty('--handwriting-font', e.target.value)
  },
  '#font-size': {
    on: 'change',
    action: (e) => {
      if (e.target.value > 30) {
        alert('Font-size is too big try upto 30');
      } else {
        setTextareaStyle('fontSize', e.target.value + 'pt');
        e.preventDefault();
      }
    }
  },
  '#letter-spacing': {
    on: 'change',
    action: (e) => {
      if (e.target.value > 40) {
        alert('Letter Spacing is too big try a number upto 40');
      } else {
        setTextareaStyle('letterSpacing', e.target.value + 'px');
        e.preventDefault();
      }
    }
  },
  '#word-spacing': {
    on: 'change',
    action: (e) => {
      if (e.target.value > 100) {
        alert('Word Spacing is too big try a number upto hundred');
      } else {
        setTextareaStyle('wordSpacing', e.target.value + 'px');
        e.preventDefault();
      }
    }
  },
  '#top-padding': {
    on: 'change',
    action: (e) => {
      document.querySelector('.page-a .paper-content').style.paddingTop =
        e.target.value + 'px';
    }
  },
  '#font-file': {
    on: 'change',
    action: (e) => addFontFromFile(e.target.files[0])
  },
  '#ink-color': {
    on: 'change',
    action: (e) => {
      document.body.style.setProperty('--ink-color', e.target.value);
      setInkColor(e.target.value);
    }
  },
  '#pen-type': {
    on: 'change',
    action: (e) => {
      document.body.style.setProperty('--pen-type-filter', e.target.value === 'fountain' ? 'blur(0.5px) contrast(1.2)' : e.target.value === 'gel' ? 'brightness(1.5) contrast(1.5)' : 'none');
      document.body.style.setProperty('--pen-type-opacity', e.target.value === 'ballpoint' ? '0.85' : '1');
    }
  },
  '#messiness': {
    on: 'change',
    action: (e) => {
      document.body.style.setProperty('--messiness-transform', e.target.value === 'high' ? 'rotate(-1.5deg) translateY(1px)' : e.target.value === 'low' ? 'rotate(0.5deg)' : 'none');
    }
  },
  '#paper-style': {
    on: 'change',
    action: (e) => {
      const pageEl = document.querySelector('.page-a');
      pageEl.classList.remove('paper-ruled', 'paper-legal', 'paper-graph', 'paper-parchment', 'paper-blank');
      pageEl.classList.add(`paper-${e.target.value}`);
    }
  },
  '#download-as-zip-button': {
    on: 'click',
    action: () => {
      // Need to invoke zip download logic
      if (typeof window.downloadAsZIP === 'function') {
        window.downloadAsZIP();
      }
    }
  },
  '#note': {
    on: 'input',
    action: () => {
      const paperContentEl = document.querySelector('.page-a .paper-content');
      const scrollHeight = paperContentEl.scrollHeight;
      const clientHeight = 514;
      const pages = Math.ceil(scrollHeight / clientHeight) || 1;
      const estimateEl = document.getElementById('page-estimate');
      if (estimateEl) estimateEl.innerText = pages;
    }
  },
  '#import-text-file': {
    on: 'change',
    action: (e) => {
      const file = e.target.files[0];
      if (file) {
        const reader = new FileReader();
        reader.onload = (ev) => {
          const text = ev.target.result.replace(/\n/g, '<br/>');
          const note = document.querySelector('#note');
          
          // Clear default dummy text if it's the only thing there
          if (note.innerHTML.includes('Lorem ipsum')) {
             note.innerHTML = text;
          } else {
             note.innerHTML += (note.innerHTML.endsWith('<br>') || note.innerHTML.endsWith('<br/>') ? '' : '<br/>') + text;
          }
          
          // Reset the input so the same file can be selected again
          e.target.value = '';
        };
        reader.readAsText(file);
      }
    }
  },
  '#import-image-file': {
    on: 'change',
    action: (e) => {
      const file = e.target.files[0];
      if (file) {
        const reader = new FileReader();
        reader.onload = (ev) => {
          const img = document.createElement('img');
          img.src = ev.target.result;
          img.style.position = 'absolute';
          img.style.top = '50px';
          img.style.left = '50px';
          img.style.maxWidth = '200px';
          img.style.cursor = 'move';
          img.style.zIndex = '10';
          img.onmousedown = function(event) {
            let shiftX = event.clientX - img.getBoundingClientRect().left;
            let shiftY = event.clientY - img.getBoundingClientRect().top;
            function moveAt(pageX, pageY) {
              const rect = document.querySelector('.page-a').getBoundingClientRect();
              const scrollTop = document.querySelector('.page-a').scrollTop;
              img.style.left = pageX - rect.left - shiftX + 'px';
              img.style.top = pageY - rect.top - shiftY + scrollTop + 'px';
            }
            function onMouseMove(event) { moveAt(event.pageX, event.pageY); }
            document.addEventListener('mousemove', onMouseMove);
            img.onmouseup = function() {
              document.removeEventListener('mousemove', onMouseMove);
              img.onmouseup = null;
            };
          };
          img.ondragstart = function() { return false; };
          document.querySelector('.page-a').appendChild(img);
        };
        reader.readAsDataURL(file);
      }
    }
  },
  '#paper-margin-toggle': {
    on: 'change',
    action: () => {
      if (pageEl.classList.contains('margined')) {
        pageEl.classList.remove('margined');
      } else {
        pageEl.classList.add('margined');
      }
    }
  },
  '#paper-line-toggle': {
    on: 'change',
    action: () => {
      if (pageEl.classList.contains('lines')) {
        pageEl.classList.remove('lines');
      } else {
        pageEl.classList.add('lines');
      }
    }
  },
  '#draw-diagram-button': {
    on: 'click',
    action: () => {
      toggleDrawCanvas();
    }
  },
  '.draw-container .close-button': {
    on: 'click',
    action: () => {
      toggleDrawCanvas();
    }
  },
  '#download-as-pdf-button': {
    on: 'click',
    action: () => {
      downloadAsPDF();
    }
  },
  '#delete-all-button': {
    on: 'click',
    action: () => {
      deleteAll();
    }
  },
  '.page-a .paper-content': {
    on: 'paste',
    action: formatText
  },
  '#paper-file': {
    on: 'change',
    action: (e) => addPaperFromFile(e.target.files[0])
  }
};

for (const eventSelector in EVENT_MAP) {
  document
    .querySelector(eventSelector)
    .addEventListener(
      EVENT_MAP[eventSelector].on,
      EVENT_MAP[eventSelector].action
    );
}

/**
 * This makes toggles, accessible.
 */
document.querySelectorAll('.switch-toggle input').forEach((toggleInput) => {
  toggleInput.addEventListener('change', (e) => {
    if (toggleInput.checked) {
      document.querySelector(
        `label[for="${toggleInput.id}"] .status`
      ).textContent = 'on';
      toggleInput.setAttribute('aria-checked', true);
    } else {
      toggleInput.setAttribute('aria-checked', false);
      document.querySelector(
        `label[for="${toggleInput.id}"] .status`
      ).textContent = 'off';
    }
  });
});

/**
 * Save and Load Presets
 */
const customInputs = document.querySelectorAll('.customization-col select, .customization-col input[type="number"], .customization-col input[type="checkbox"]');

function savePresets() {
  const presets = {};
  customInputs.forEach(input => {
    if (input.type === 'checkbox') {
      presets[input.id] = input.checked;
    } else {
      presets[input.id] = input.value;
    }
  });
  localStorage.setItem('handwriting-presets', JSON.stringify(presets));
}

function loadPresets() {
  const saved = localStorage.getItem('handwriting-presets');
  if (saved) {
    const presets = JSON.parse(saved);
    customInputs.forEach(input => {
      if (presets[input.id] !== undefined) {
        if (input.type === 'checkbox') {
          input.checked = presets[input.id];
        } else {
          input.value = presets[input.id];
        }
        // Dispatch change event to trigger updates
        input.dispatchEvent(new Event('change'));
      }
    });
  }
}

customInputs.forEach(input => {
  input.addEventListener('change', savePresets);
});

// Load presets on init after a tiny delay to ensure bindings are complete
setTimeout(loadPresets, 100);
