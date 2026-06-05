function buildEmptyOption(title) {
  return {
    title: {
      text: title || ''
    },
    series: []
  };
}

module.exports = {
  buildEmptyOption
};
