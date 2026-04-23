function copyLink() {
    const link = document.getElementById("shortLink").innerText;
    navigator.clipboard.writeText(link);
    alert("Copied to clipboard!");
}
