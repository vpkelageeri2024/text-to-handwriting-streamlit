import {
  applyPaperStyles,
  removePaperStyles,
  renderOutput
} from './utils/generate-utils.mjs';
import { createPDF } from './utils/helpers.mjs';

const pageEl = document.querySelector('.page-a');
let outputImages = [];

/**
 * To generate image, we add styles to DIV and converts that HTML Element into Image.
 * This is the function that deals with it.
 */
async function convertDIVToImage() {
  const options = {
    scrollX: 0,
    scrollY: -window.scrollY,
    scale: document.querySelector('#resolution').value,
    useCORS: true
  };

  /** Function html2canvas comes from a library html2canvas which is included in the index.html */
  const canvas = await html2canvas(pageEl, options);

  /** Send image data for modification if effect is scanner */
  if (document.querySelector('#page-effects').value === 'scanner') {
    const context = canvas.getContext('2d');
    const imageData = context.getImageData(0, 0, canvas.width, canvas.height);
    contrastImage(imageData, 0.55);
    canvas.getContext('2d').putImageData(imageData, 0, 0);
  }

  outputImages.push(canvas);
  // Displaying no. of images on addition
  if (outputImages.length >= 1) {
    document.querySelector('#output-header').textContent =
      'Output ' + '( ' + outputImages.length + ' )';
  }
}

/**
 * This is the function that gets called on clicking "Generate Image" button.
 */
export async function generateImages() {
  applyPaperStyles();
  pageEl.scroll(0, 0);

  const paperContentEl = document.querySelector('.page-a .paper-content');
  
  function applyJitterToHTML(html) {
    const messiness = document.querySelector('#messiness').value;
    if (messiness === 'none') return html;
    
    const intensity = messiness === 'high' ? 2 : 1;
    return html.replace(/(>|^)([^<]+)(<|$)/g, (match, p1, p2, p3) => {
      const jitteredWords = p2.split(/(\s+)/).map(word => {
        if (!word.trim()) return word; // preserve spaces intact
        const rot = (Math.random() * 2 - 1) * intensity * 1.5; // -1.5 to +1.5 deg
        const dy = (Math.random() * 2 - 1) * intensity * 1; // -1 to +1 px
        return `<span style="display:inline-block; transform: rotate(${rot}deg) translateY(${dy}px);">${word}</span>`;
      }).join('');
      return p1 + jitteredWords + p3;
    });
  }

  const scrollHeight = paperContentEl.scrollHeight;
  const clientHeight = 514; // height of .paper-content when there is no content

  const totalPages = Math.ceil(scrollHeight / clientHeight);

  if (totalPages > 1) {
    // For multiple pages
    if (paperContentEl.innerHTML.includes('<img')) {
      alert(
        "You're trying to generate more than one page, Images and some formatting may not work correctly with multiple images" // eslint-disable-line max-len
      );
    }
    const initialPaperContent = paperContentEl.innerHTML;
    const splitContent = initialPaperContent.split(/(\s+|<br\s*\/?>)/);

    // multiple images
    let wordCount = 0;
    while (wordCount < splitContent.length) {
      let low = wordCount;
      let high = splitContent.length;
      let best = wordCount;
      
      while (low <= high) {
        let mid = Math.floor((low + high) / 2);
        paperContentEl.innerHTML = splitContent.slice(wordCount, mid).join('');
        if (paperContentEl.scrollHeight <= clientHeight) {
          best = mid;
          low = mid + 1;
        } else {
          high = mid - 1;
        }
      }
      
      // best is the maximum index without exceeding height
      // If a single token is too large, force it to prevent infinite loop
      if (best === wordCount) {
        best = wordCount + 1;
      }
      
      const rawHTML = splitContent.slice(wordCount, best).join('');
      paperContentEl.innerHTML = applyJitterToHTML(rawHTML);
      wordCount = best;
      
      pageEl.scrollTo(0, 0);
      await convertDIVToImage();
    }
    paperContentEl.innerHTML = initialPaperContent;
  } else {
    // single image
    const initialPaperContent = paperContentEl.innerHTML;
    paperContentEl.innerHTML = applyJitterToHTML(initialPaperContent);
    await convertDIVToImage();
    paperContentEl.innerHTML = initialPaperContent;
  }

  removePaperStyles();
  renderOutput(outputImages);
  setRemoveImageListeners();
}

/**
 * Delete all generated images
 */

export const deleteAll = () => {
  outputImages.splice(0, outputImages.length);
  renderOutput(outputImages);
  document.querySelector('#output-header').textContent =
    'Output' + (outputImages.length ? ' ( ' + outputImages.length + ' )' : '');
};

const arrayMove = (arr, oldIndex, newIndex) => {
  if (newIndex >= arr.length) {
    let k = newIndex - arr.length + 1;
    while (k--) {
      arr.push(undefined);
    }
  }
  arr.splice(newIndex, 0, arr.splice(oldIndex, 1)[0]);
  return arr; // for testing
};

export const moveLeft = (index) => {
  if (index === 0) return outputImages;
  outputImages = arrayMove(outputImages, index, index - 1);
  renderOutput(outputImages);
};

export const moveRight = (index) => {
  if (index + 1 === outputImages.length) return outputImages;
  outputImages = arrayMove(outputImages, index, index + 1);
  renderOutput(outputImages);
};

/**
 * Downloads generated images as PDF
 */
export const downloadAsPDF = () => createPDF(outputImages);

export const downloadAsZIP = () => {
  if (!outputImages.length) return alert('No images to download');
  const zip = new JSZip();
  outputImages.forEach((base64Url, index) => {
    const base64Data = base64Url.split(',')[1];
    zip.file(`handwritten-page-${index + 1}.jpeg`, base64Data, { base64: true });
  });
  zip.generateAsync({ type: 'blob' }).then((content) => {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(content);
    a.download = 'handwritten-notes.zip';
    a.click();
  });
};

/**
 * Sets event listeners for close button on output images.
 */
function setRemoveImageListeners() {
  document
    .querySelectorAll('.output-image-container > .close-button')
    .forEach((closeButton) => {
      closeButton.addEventListener('click', (e) => {
        outputImages.splice(Number(e.target.dataset.index), 1);
        // Displaying no. of images on deletion
        if (outputImages.length >= 0) {
          document.querySelector('#output-header').textContent =
            'Output' +
            (outputImages.length ? ' ( ' + outputImages.length + ' )' : '');
        }
        renderOutput(outputImages);
        // When output changes, we have to set remove listeners again
        setRemoveImageListeners();
      });
    });

  document.querySelectorAll('.move-left').forEach((leftButton) => {
    leftButton.addEventListener('click', (e) => {
      moveLeft(Number(e.target.dataset.index));
      // Displaying no. of images on deletion
      renderOutput(outputImages);
      // When output changes, we have to set remove listeners again
      setRemoveImageListeners();
    });
  });

  document.querySelectorAll('.move-right').forEach((rightButton) => {
    rightButton.addEventListener('click', (e) => {
      moveRight(Number(e.target.dataset.index));
      // Displaying no. of images on deletion
      renderOutput(outputImages);
      // When output changes, we have to set remove listeners again
      setRemoveImageListeners();
    });
  });
}

/** Modifies image data to add contrast */

function contrastImage(imageData, contrast) {
  const data = imageData.data;
  contrast *= 255;
  const factor = (contrast + 255) / (255.01 - contrast);
  for (let i = 0; i < data.length; i += 4) {
    data[i] = factor * (data[i] - 128) + 128;
    data[i + 1] = factor * (data[i + 1] - 128) + 128;
    data[i + 2] = factor * (data[i + 2] - 128) + 128;
  }
  return imageData;
}
