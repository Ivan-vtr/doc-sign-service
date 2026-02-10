document.addEventListener('DOMContentLoaded', function() {
    var dropZone = document.getElementById('drop-zone');
    var fileInput = document.getElementById('file-input');
    var titleInput = document.getElementById('upload-title');
    var packageSelect = document.getElementById('package-select');
    var resultsList = document.getElementById('upload-results');

    if (!dropZone) return;

    dropZone.addEventListener('dragover', function(e) {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    });

    dropZone.addEventListener('dragleave', function() {
        dropZone.classList.remove('drag-over');
    });

    dropZone.addEventListener('drop', function(e) {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
        handleFiles(e.dataTransfer.files);
    });

    dropZone.addEventListener('click', function() {
        fileInput.click();
    });

    fileInput.addEventListener('change', function() {
        handleFiles(fileInput.files);
    });

    async function handleFiles(files) {
        if (!files.length) return;

        var title = titleInput.value.trim();
        var packageId = packageSelect ? packageSelect.value : '';

        if (files.length === 1) {
            await uploadSingle(files[0], title || files[0].name, packageId);
        } else {
            await uploadMultiple(files, title, packageId);
        }

        // Reset input
        fileInput.value = '';
    }

    async function uploadSingle(file, title, packageId) {
        var formData = new FormData();
        formData.append('file', file);
        formData.append('title', title);
        if (packageId) {
            formData.append('package_id', packageId);
        }

        showProgress(file.name);

        try {
            var result = await apiFetch('/api/documents/upload/', {
                method: 'POST',
                body: formData,
            });
            showResult(result.title || result.filename, result.document_id, true);
        } catch (e) {
            showResult(file.name + ': ' + e.message, null, false);
        }
    }

    async function uploadMultiple(files, title, packageId) {
        var formData = new FormData();
        for (var i = 0; i < files.length; i++) {
            formData.append('files', files[i]);
        }
        if (title) {
            formData.append('title', title);
        }
        if (packageId) {
            formData.append('package_id', packageId);
        }

        showProgress(files.length + ' файлов');

        try {
            var result = await apiFetch('/api/documents/upload-multiple/', {
                method: 'POST',
                body: formData,
            });
            for (var i = 0; i < result.documents.length; i++) {
                var doc = result.documents[i];
                if (doc.error) {
                    showResult((doc.filename || 'Файл') + ': ' + doc.error, null, false);
                } else {
                    showResult(doc.title || doc.filename, doc.document_id, true);
                }
            }
        } catch (e) {
            showResult('Ошибка загрузки: ' + e.message, null, false);
        }

        removeProgress();
    }

    function showProgress(label) {
        removeProgress();
        var div = document.createElement('div');
        div.id = 'upload-progress';
        div.className = 'alert alert-info';
        div.innerHTML = '<span class="loading-spinner me-2"></span> Загрузка: ' + label + '...';
        resultsList.prepend(div);
    }

    function removeProgress() {
        var el = document.getElementById('upload-progress');
        if (el) el.remove();
    }

    function showResult(label, docId, success) {
        removeProgress();
        var div = document.createElement('div');
        div.className = 'alert alert-' + (success ? 'success' : 'danger') + ' mt-2';
        if (success && docId) {
            div.innerHTML = 'Загружено: <strong>' + label + '</strong> ' +
                '<a href="/documents/' + docId + '/" class="btn btn-sm btn-outline-primary ms-2">Просмотр</a> ' +
                '<a href="/documents/' + docId + '/sign/" class="btn btn-sm btn-outline-success ms-2">Подписать</a>';
        } else {
            div.textContent = success ? 'Загружено: ' + label : 'Ошибка: ' + label;
        }
        resultsList.prepend(div);
    }
});
