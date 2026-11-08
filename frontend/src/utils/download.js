// Shared browser download helpers: save a Blob or a text string as a file.

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Revoke later: some browsers (Safari) cancel the download if the URL is revoked immediately.
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}

export function downloadTextFile(filename, content) {
  downloadBlob(new Blob([content], { type: 'text/plain;charset=utf-8' }), filename);
}
