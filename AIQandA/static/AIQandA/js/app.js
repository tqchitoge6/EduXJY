(function () {
  "use strict";

  function csrfToken() {
    var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return input ? input.value : "";
  }

  function setupSidebar() {
    var toggle = document.getElementById("menu-toggle");
    var backdrop = document.getElementById("sidebar-backdrop");
    if (!toggle || !backdrop) {
      return;
    }
    function close() {
      document.body.classList.remove("sidebar-open");
    }
    toggle.addEventListener("click", function () {
      document.body.classList.toggle("sidebar-open");
    });
    backdrop.addEventListener("click", close);
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        close();
      }
    });
  }

  function autoGrow(textarea) {
    textarea.style.height = "auto";
    textarea.style.height = Math.min(textarea.scrollHeight, 150) + "px";
  }

  function setupComposer() {
    var textarea = document.getElementById("question-input");
    if (!textarea) {
      return;
    }
    textarea.addEventListener("input", function () {
      autoGrow(textarea);
    });
    autoGrow(textarea);
  }

  function setFeedbackState(container, rating) {
    var buttons = container.querySelectorAll(".feedback-button");
    buttons.forEach(function (button) {
      button.classList.toggle("selected", button.dataset.rating === rating);
    });
    var note = container.querySelector(".feedback-note");
    if (note) {
      note.textContent = "已记录反馈";
    }
  }

  function submitFeedback(button) {
    var container = button.closest(".feedback");
    if (!container || container.dataset.pending === "1") {
      return;
    }
    var messageId = container.dataset.messageId;
    var rating = button.dataset.rating;
    if (!messageId || !rating) {
      return;
    }
    container.dataset.pending = "1";
    fetch("/api/messages/" + messageId + "/feedback/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken()
      },
      body: JSON.stringify({ rating: rating, comment: "" })
    })
      .then(function (response) {
        return response.json().then(function (data) {
          if (!response.ok) {
            throw new Error(data.error || "反馈提交失败");
          }
          return data;
        });
      })
      .then(function (data) {
        setFeedbackState(container, data.rating);
      })
      .catch(function (error) {
        var note = container.querySelector(".feedback-note");
        if (note) {
          note.textContent = error.message || "反馈提交失败";
        }
      })
      .finally(function () {
        delete container.dataset.pending;
      });
  }

  document.addEventListener("click", function (event) {
    var feedbackButton = event.target.closest(".feedback-button");
    if (feedbackButton) {
      submitFeedback(feedbackButton);
    }
  });

  document.addEventListener("DOMContentLoaded", function () {
    setupSidebar();
    setupComposer();
  });
})();
