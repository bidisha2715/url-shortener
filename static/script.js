function copyLink(btn) {
    const input = document.getElementById("shortLink");
    navigator.clipboard.writeText(input.value);

    btn.innerText = "Copied!";
    setTimeout(() => btn.innerText = "Copy", 1500);
}
