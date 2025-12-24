document.getElementById("btn_fetch")?.addEventListener("click", async () => {
    const url = document.getElementById('url_input').value.trim();
    if (!url) return alert("Please paste the URL.");
    
    btn.disabled = true;
    btn.innerText = "Retrieving data...";
    
    const response = await fetch(`/fetch_url?url=${encodeURIComponent(url)}`);
    const data = await response.json();
    
    try {
        if (data.error || !data.title) {
            alert("Failed to retrieve data.");
        }

        document.getElementById("title").value = data.title || "";
        document.getElementById("description").value = data.description || "";
        
        const img = document.getElementById("item_image");
        const hidden = document.getElementById("img_url_hidden");
        if (data.image) {
            img.src = data.image;
            img.style.display = "block";
            hidden.value = data.image;
        }
        alert("Data retrieved successfully.");
    } catch (error) {
        console.error(error);
        alert("Failed to retrieve data.");
    } finally {
        btn.disabled = false;
        btn.innerText = "Auto Fill";
    }
});