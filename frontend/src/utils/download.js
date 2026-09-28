// Déclenche le téléchargement d'une réponse Axios reçue en blob.
// (On passe par un blob car les endpoints sont protégés par JWT : un simple
//  <a href> n'enverrait pas le header Authorization.)
export function saveBlob(response, fallbackName) {
  const blob = new Blob([response.data], { type: response.headers['content-type'] || 'application/octet-stream' });

  // Récupère le nom de fichier depuis Content-Disposition si présent.
  let filename = fallbackName;
  const cd = response.headers['content-disposition'];
  if (cd) {
    const match = cd.match(/filename="?([^"]+)"?/);
    if (match) filename = match[1];
  }

  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}
