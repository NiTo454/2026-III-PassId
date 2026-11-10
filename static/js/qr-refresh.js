const qrImage = document.querySelector("[data-qr-refresh-url]");

if (qrImage) {
    const qrRefreshUrl = new URL(
        qrImage.dataset.qrRefreshUrl,
        window.location.origin,
    );

    window.setInterval(() => {
        qrRefreshUrl.searchParams.set("refresh", Date.now());
        qrImage.src = qrRefreshUrl.toString();
    }, 240000);
}
