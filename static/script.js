document.addEventListener("DOMContentLoaded", function() {
    
    initAutoFill();
    initImagePreview();
    initValidation();
    initAlertAutoClose();
    initDeleteConfirmation();
    initDoneConfirmation();
});

function initImagePreview() {
    const imgInput = document.getElementById("img_url_input");
    const imgPreview = document.getElementById("item_image");

    if (imgInput && imgPreview) {
        imgInput.addEventListener("input", function() {
            imgPreview.src = this.value;
            imgPreview.style.display = this.value ? "block" : "none";
        });
    } 
}

function initValidation() {
    const form = document.querySelector('form[action="/order"], form[action^="/edit_bounty"]');
    if (!form) return;

    document.addEventListener('submit', function(e) {
        const priceInput = form.querySelector('input[name="price"]');
        const rewardInput = form.querySelector('input[name="reward"]');

        if (priceInput && rewardInput) {
            const price = parseFloat(priceInput.value) || 0;
            const reward = parseFloat(rewardInput.value) || 0;
            
            if (price < 0 || reward < 0) {
                e.preventDefault();
                alert("Price and reward must be non-negative numbers.");
            }
        }
    });
}

function initAutoFill() {
    document.getElementById("btn_fetch")?.addEventListener("click", async () => {
        const url = document.getElementById('url_input').value.trim();
        if (!url) return alert("Please paste the URL.");

        toggleLoadingState(true);

        try {
            const response = await fetch(`/fetch_url?url=${encodeURIComponent(url)}`);
            if (!response.ok) throw new Error("Network response was not ok");
            const data = await response.json();
            fillFormFields(data);
        } catch (error) {
            console.error(error);
            alert("Failed to retrieve data.");
        } finally {
            toggleLoadingState(false);
        }
    });
}

function toggleLoadingState(isLoading) {
    const btn = document.getElementById("btn_fetch");
    const btnText = document.getElementById("btn_text");
    const btnSpinner = document.getElementById("btn_spinner");

    if (btn && btnText && btnSpinner) {
        btn.disabled = isLoading;
        if (isLoading) {
            btnText.classList.add("d-none");
            btnSpinner.classList.remove("d-none");
        } else {
            btnText.classList.remove("d-none");
            btnSpinner.classList.add("d-none");
        }
    }
}

function fillFormFields(data) {
    if (data.error || !data.title) {
        alert("Could not retrieve data. Please fill manually.");
        return;
    }
    
    const nameInput = document.getElementById("item_name");
    const descInput = document.getElementById("item_description");
    const imgUrlInput = document.getElementById("img_url_input");
    const imgPreview = document.getElementById("item_image");

    if (nameInput) nameInput.value = data.title || "";
    if (descInput) descInput.value = data.description || "";
    
    if (data.image && imgPreview) {
        imgPreview.src = data.image;
        imgPreview.style.display = "block";
        if (imgUrlInput) imgUrlInput.value = data.image;
    } else if (imgPreview) {
        imgPreview.style.display = "none";
        imgPreview.src = "";
        if (imgUrlInput) imgUrlInput.value = "/static/Bountygo.png";
    }
}

function initDeleteConfirmation() {
    let formToDelete = null;

    document.querySelectorAll('.btn-delete-trigger').forEach(button => {
        button.addEventListener('click', function() {
            formToDelete = button.closest('form');
        });
    });

    const confirmBtn = document.getElementById('confirmDeleteBtn');
    if (confirmBtn) {
        confirmBtn.addEventListener('click', () => {
            if (formToDelete) formToDelete.submit();
        });
    } 
}

function initDoneConfirmation() {
    let formToDone = null;

    document.querySelectorAll('.btn-done-trigger').forEach(button => {
        button.addEventListener('click', function() {
            formToDone = button.closest('form');
        });
    });

    const confirmBtn = document.getElementById('confirmdoneBtn');
    if (confirmBtn) {
        confirmBtn.addEventListener('click', () => {
            if (formToDone) formToDone.submit();
        });
    } 
}

function initAlertAutoClose() {
    document.querySelectorAll('.alert-dismissible').forEach(alert => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 3000);
    });
}