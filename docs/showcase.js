// No requests, analytics, or dependencies: the same tour works as a local HTML file.
const root = document.documentElement
const themeButtons = document.querySelectorAll('[data-set-theme]')
const dialog = document.querySelector('#image-viewer')
const viewerImage = document.querySelector('#viewer-image')
const imageWrap = document.querySelector('.viewer-image-wrap')
let theme = 'light'

function setTheme(next) {
  theme = next === 'dark' ? 'dark' : 'light'
  root.dataset.theme = theme
  themeButtons.forEach((button) => {
    button.setAttribute('aria-pressed', String(button.dataset.setTheme === theme))
  })
  document.querySelectorAll('.theme-caption').forEach((caption) => {
    caption.textContent = theme === 'dark' ? 'Dark theme' : 'Light theme'
  })
  try {
    localStorage.setItem('mailcow-showcase-theme', theme)
  } catch {
    // Storage may be unavailable for local files or private browsing.
  }
}

let initialTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
try {
  initialTheme = localStorage.getItem('mailcow-showcase-theme') || initialTheme
} catch {
  // The tour remains usable without browser storage.
}
setTheme(initialTheme)
document.querySelector('.theme-control').hidden = false
themeButtons.forEach((button) => {
  button.addEventListener('click', () => setTheme(button.dataset.setTheme))
})

document.querySelectorAll('.screenshot').forEach((button) => {
  button.addEventListener('click', () => {
    const image = button.querySelector(`[data-theme-image="${theme}"]`)
    viewerImage.src = image.src
    viewerImage.alt = image.alt
    document.querySelector('#viewer-title').textContent = button.dataset.title
    document.querySelector('#viewer-description').textContent = button.dataset.description
    imageWrap.classList.remove('full-size')
    imageWrap.setAttribute('aria-pressed', 'false')
    dialog.showModal()
    document.body.classList.add('viewer-open')
    imageWrap.scrollTo(0, 0)
  })
})

document.querySelector('#close-viewer').addEventListener('click', () => dialog.close())
dialog.addEventListener('close', () => document.body.classList.remove('viewer-open'))
dialog.addEventListener('click', (event) => {
  if (event.target !== dialog) return
  const rect = dialog.getBoundingClientRect()
  if (
    event.clientX < rect.left ||
    event.clientX > rect.right ||
    event.clientY < rect.top ||
    event.clientY > rect.bottom
  ) {
    dialog.close()
  }
})

imageWrap.tabIndex = 0
imageWrap.setAttribute('role', 'button')
imageWrap.setAttribute('aria-label', 'Toggle screenshot between fit and full size')
imageWrap.setAttribute('aria-pressed', 'false')
function toggleImageSize() {
  imageWrap.setAttribute('aria-pressed', String(imageWrap.classList.toggle('full-size')))
}
imageWrap.addEventListener('click', toggleImageSize)
imageWrap.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    toggleImageSize()
  }
})

// Saving an offline copy again preserves its embedded assets and selected theme.
if (root.dataset.standalone === 'true') {
  document.querySelectorAll('[data-download]').forEach((link) => {
    link.addEventListener('click', (event) => {
      event.preventDefault()
      const snapshot = document.documentElement.cloneNode(true)
      snapshot.querySelector('#image-viewer').removeAttribute('open')
      snapshot.querySelector('body').classList.remove('viewer-open')
      snapshot.querySelector('#viewer-image').removeAttribute('src')
      const blob = new window.Blob(['<!doctype html>\n', snapshot.outerHTML], {
        type: 'text/html;charset=utf-8',
      })
      const url = window.URL.createObjectURL(blob)
      const download = document.createElement('a')
      download.href = url
      download.download = 'mailcow-modern-ui-showcase.html'
      document.body.append(download)
      download.click()
      download.remove()
      window.setTimeout(() => window.URL.revokeObjectURL(url), 1000)
    })
  })
}
