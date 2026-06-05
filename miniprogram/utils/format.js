function formatText(value) {
  if (value === null || value === undefined) {
    return '';
  }
  return String(value);
}

module.exports = {
  formatText
};
