// File drag and drop logic
document.addEventListener('DOMContentLoaded', function() {
  const fileInput = document.getElementById('file');
  const fileMsg = document.querySelector('.file-msg');
  const dropArea = document.querySelector('.file-drop-area');

  if (fileInput && fileMsg && dropArea) {
    fileInput.addEventListener('change', function(e) {
      let fileName = e.target.files[0] ? e.target.files[0].name : "Choose a .c or .cpp file or drag it here";
      fileMsg.textContent = fileName;
    });

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
      dropArea.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
      e.preventDefault();
      e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
      dropArea.addEventListener(eventName, () => dropArea.classList.add('dragover'), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
      dropArea.addEventListener(eventName, () => dropArea.classList.remove('dragover'), false);
    });

    dropArea.addEventListener('drop', handleDrop, false);

    function handleDrop(e) {
      let dt = e.dataTransfer;
      let files = dt.files;
      fileInput.files = files;
      let fileName = files[0] ? files[0].name : "Choose a .c or .cpp file or drag it here";
      fileMsg.textContent = fileName;
    }
  }

  // Tab switching logic
  const tabBar = document.getElementById('tabBar');
  if (tabBar) {
    tabBar.addEventListener('click', function (e) {
      const btn = e.target.closest('.tab');
      if (!btn) return;

      document.querySelectorAll('.tab').forEach(function (t) {
        t.classList.remove('active');
      });
      document.querySelectorAll('.tab-pane').forEach(function (p) {
        p.classList.remove('active');
      });

      btn.classList.add('active');
      const targetPane = document.getElementById(btn.dataset.target);
      if (targetPane) {
        targetPane.classList.add('active');
      }
    });
  }
});