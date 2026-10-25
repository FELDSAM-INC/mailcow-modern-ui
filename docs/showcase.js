// No requests, analytics, or dependencies: the same tour works as a local HTML file.
const root = document.documentElement
const themeButtons = document.querySelectorAll('[data-set-theme]')
const dialog = document.querySelector('#image-viewer')
const viewerImage = document.querySelector('#viewer-image')
const imageWrap = document.querySelector('.viewer-image-wrap')
let theme = 'light'
let accent = null
try {
  const saved = localStorage.getItem('mailcow-showcase-accent')
  if (/^#[a-f\d]{6}$/i.test(saved || '')) accent = saved
} catch { /* Browser storage is optional. */ }

function applyAccent() {
  for (const variable of ['--green', '--on-green', '--tint']) root.style.removeProperty(variable)
  const colour = accent || (theme === 'dark' ? '#53c58a' : '#18794e')
  if (accent) {
    root.style.setProperty('--green', accent)
    const channels = [1, 3, 5].map((offset) => Number.parseInt(accent.slice(offset, offset + 2), 16))
    const brightness = channels[0] * 0.299 + channels[1] * 0.587 + channels[2] * 0.114
    root.style.setProperty('--on-green', brightness > 150 ? '#14181d' : '#ffffff')
    root.style.setProperty('--tint', 'color-mix(in srgb, var(--green) 12%, var(--surface))')
  }
  document.querySelector('#accent-colour').value = colour
  document.querySelector('#accent-value').textContent = colour.toUpperCase()
}

function selectAccent(value) {
  accent = /^#[a-f\d]{6}$/i.test(value || '') ? value : null
  try {
    if (accent) localStorage.setItem('mailcow-showcase-accent', accent)
    else localStorage.removeItem('mailcow-showcase-accent')
  } catch { /* Preview still works without storage. */ }
  applyAccent()
}

function setTheme(next) {
  theme = next === 'dark' ? 'dark' : 'light'
  root.dataset.theme = theme
  applyAccent()
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

document.querySelector('#accent-colour').addEventListener('input', (event) => selectAccent(event.target.value))
document.querySelector('#reset-accent').addEventListener('click', () => selectAccent(null))
document.querySelectorAll('[data-accent]').forEach((button) => {
  button.addEventListener('click', () => selectAccent(button.dataset.accent))
})
const installMenu = document.querySelector('.install-menu')
document.addEventListener('click', (event) => {
  if (!installMenu.contains(event.target)) installMenu.open = false
})
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && installMenu.open) {
    installMenu.open = false
    installMenu.querySelector('summary').focus()
  }
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
