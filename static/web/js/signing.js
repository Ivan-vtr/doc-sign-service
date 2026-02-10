document.addEventListener('DOMContentLoaded', function() {
    var container = document.getElementById('signing-container');
    if (!container) return;
    startSigningFlow();
});

async function startSigningFlow() {
    var container = document.getElementById('signing-container');
    var documentId = container.dataset.documentId;
    var packageId = container.dataset.packageId;
    var isPackage = !!packageId;

    var statusEl = document.getElementById('signing-status');
    var spinnerEl = document.getElementById('signing-spinner');
    var qrSection = document.getElementById('qr-section');
    var qrEl = document.getElementById('qr-image');
    var linksEl = document.getElementById('signing-links');
    var resultEl = document.getElementById('signing-result');

    try {
        // Step 1: Initiate signing
        statusEl.textContent = 'Инициализация сессии подписания...';
        spinnerEl.style.display = 'inline-block';

        var initiateUrl = isPackage
            ? '/api/signing/package/initiate/'
            : '/api/signing/initiate/';
        var initiateBody = isPackage
            ? {package_id: packageId}
            : {document_id: documentId};

        var initResult = await apiFetch(initiateUrl, {
            method: 'POST',
            body: JSON.stringify(initiateBody),
        });

        // Step 2: Display QR code and deep links
        qrSection.style.display = '';
        qrEl.src = 'data:image/gif;base64,' + initResult.qr_code_base64;
        qrEl.style.display = 'block';

        var linksHtml = '<div class="d-flex flex-column flex-sm-row gap-2 justify-content-center">';
        if (initResult.egov_mobile_link) {
            linksHtml += '<a href="' + initResult.egov_mobile_link + '" class="deep-link-btn deep-link-egov">' +
                'eGov Mobile</a>';
        }
        if (initResult.egov_business_link) {
            linksHtml += '<a href="' + initResult.egov_business_link + '" class="deep-link-btn deep-link-business">' +
                'eGov Business</a>';
        }
        linksHtml += '</div>';
        linksEl.innerHTML = linksHtml;

        statusEl.textContent = 'Отсканируйте QR-код приложением eGov Mobile...';

        // Step 3: Call complete (long-polling - blocks until user scans)
        var completeUrl = isPackage
            ? '/api/signing/package/complete/'
            : '/api/signing/complete/';
        var completeBody = isPackage
            ? {
                package_id: packageId,
                session_id: initResult.session_id,
                data_url: initResult.data_url,
                sign_url: initResult.sign_url,
            }
            : {
                document_id: documentId,
                session_id: initResult.session_id,
                data_url: initResult.data_url,
                sign_url: initResult.sign_url,
            };

        var completeResult = await apiFetch(completeUrl, {
            method: 'POST',
            body: JSON.stringify(completeBody),
        });

        // Step 4: Success
        spinnerEl.style.display = 'none';
        qrSection.style.display = 'none';
        statusEl.textContent = 'Подписано успешно!';
        statusEl.className = 'signing-status';
        statusEl.style.color = 'var(--success)';

        var backUrl, backLabel;
        var downloadSignedUrl = '';
        if (isPackage) {
            backUrl = '/packages/' + packageId + '/';
            backLabel = 'Просмотр пакета';
        } else {
            var docId = completeResult.document_id || documentId;
            backUrl = '/documents/' + docId + '/';
            backLabel = 'Просмотр документа';
            downloadSignedUrl = '/api/documents/' + docId + '/download-signed/';
        }

        // Auto-download signed file
        if (downloadSignedUrl) {
            var downloadLink = document.createElement('a');
            downloadLink.href = downloadSignedUrl;
            downloadLink.style.display = 'none';
            document.body.appendChild(downloadLink);
            downloadLink.click();
            document.body.removeChild(downloadLink);
        }

        var signerInfo = completeResult.signer ? '<p style="margin-bottom:.75rem"><strong>Подписано:</strong> ' + completeResult.signer + '</p>' : '';
        var downloadBtn = downloadSignedUrl
            ? '<a href="' + downloadSignedUrl + '" class="btn-action ms-2">Скачать подписанный файл</a> '
            : '';
        resultEl.innerHTML =
            '<div class="alert alert-success mt-3">' +
            signerInfo +
            '<a href="' + backUrl + '" class="btn btn-brand">' + backLabel + '</a> ' +
            downloadBtn +
            '<a href="/" class="btn-action ms-2">К документам</a>' +
            '</div>';

    } catch (error) {
        spinnerEl.style.display = 'none';
        qrSection.style.display = 'none';
        statusEl.textContent = 'Ошибка подписания';
        statusEl.className = 'signing-status';
        statusEl.style.color = 'var(--danger)';
        resultEl.innerHTML =
            '<div class="alert alert-danger mt-3">' +
            '<p>' + error.message + '</p>' +
            '<button id="retry-signing-btn" class="btn btn-brand me-2">Повторить подписание</button>' +
            '<a href="/" class="btn-action">К документам</a>' +
            '</div>';
        document.getElementById('retry-signing-btn').addEventListener('click', function() {
            resultEl.innerHTML = '';
            statusEl.style.color = '';
            startSigningFlow();
        });
    }
}
