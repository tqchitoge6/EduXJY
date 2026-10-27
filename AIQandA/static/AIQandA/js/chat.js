(function () {
  "use strict";

  var config = window.AIQANDA || {};
  var scrollArea = document.getElementById("chat-scroll");
  var form = document.getElementById("ask-form");
  var input = document.getElementById("question-input");
  var sendButton = document.getElementById("send-button");
  var conversationId = config.conversationId || "";
  var isSending = false;

  if (!scrollArea || !form || !input || !sendButton) {
    return;
  }

  function element(tag, className, text) {
    var node = document.createElement(tag);
    if (className) {
      node.className = className;
    }
    if (text !== undefined && text !== null) {
      node.textContent = text;
    }
    return node;
  }

  function scrollToBottom() {
    scrollArea.scrollTop = scrollArea.scrollHeight;
  }

  function csrfToken() {
    var token = form.querySelector('input[name="csrfmiddlewaretoken"]');
    return token ? token.value : "";
  }

  function removeEmptyState() {
    var empty = document.getElementById("empty-state");
    if (empty) {
      empty.remove();
    }
  }

  function buildCitations(citations) {
    if (!citations || !citations.length) {
      return null;
    }
    var details = element("details", "citations");
    var summary = element("summary");
    summary.appendChild(element("span", "citation-icon", "⌕"));
    summary.appendChild(document.createTextNode(" 查看 " + citations.length + " 条资料来源 "));
    summary.appendChild(element("span", "summary-chevron", "⌄"));
    details.appendChild(summary);

    var list = element("div", "citation-list");
    citations.forEach(function (citation) {
      var item = element("div", "citation-item");
      var head = element("div", "citation-head");
      head.appendChild(element("span", "citation-rank", "[" + citation.index + "]"));
      head.appendChild(element("strong", "", citation.document));
      if (citation.page) {
        head.appendChild(element("span", "", "第 " + citation.page + " 页"));
      }
      head.appendChild(
        element("span", "citation-score", "相关度 " + Number(citation.score).toFixed(2))
      );
      item.appendChild(head);
      item.appendChild(element("p", "", citation.quote));
      list.appendChild(item);
    });
    details.appendChild(list);
    return details;
  }

  function buildFeedback(messageId) {
    var feedback = element("div", "feedback");
    feedback.dataset.messageId = messageId;
    feedback.appendChild(element("span", "feedback-label", "这个回答有帮助吗？"));

    ["up", "down"].forEach(function (rating) {
      var button = element(
        "button",
        "feedback-button",
        rating === "up" ? "有帮助" : "需改进"
      );
      button.type = "button";
      button.dataset.rating = rating;
      feedback.appendChild(button);
    });
    feedback.appendChild(element("span", "feedback-note", ""));
    return feedback;
  }

  function appendMessage(role, content, options) {
    options = options || {};
    removeEmptyState();
    var article = element("article", "message message-" + role);
    if (options.messageId) {
      article.dataset.messageId = options.messageId;
    }
    var avatar = element(
      "div",
      "message-avatar " + (role === "assistant" ? "assistant-avatar" : "user-message-avatar"),
      role === "assistant" ? "知" : (config.userInitial || "我")
    );
    article.appendChild(avatar);

    var body = element("div", "message-body");
    var meta = element("div", "message-meta");
    meta.appendChild(element("strong", "", role === "assistant" ? "知行助教" : "我"));
    meta.appendChild(element("span", "", "刚刚"));
    if (role === "assistant") {
      var mode = element(
        "span",
        "mode-badge" + (options.mode === "fallback" ? " mode-fallback" : ""),
        options.mode === "fallback" ? "检索降级" : "AI 生成"
      );
      meta.appendChild(mode);
    }
    body.appendChild(meta);
    body.appendChild(element("div", "message-content", content));

    if (role === "assistant") {
      var citations = buildCitations(options.citations);
      if (citations) {
        body.appendChild(citations);
      }
      if (options.messageId) {
        body.appendChild(buildFeedback(options.messageId));
      }
    }
    article.appendChild(body);
    scrollArea.appendChild(article);
    scrollToBottom();
    return article;
  }

  function appendTyping() {
    removeEmptyState();
    var article = element("article", "message message-assistant");
    article.id = "typing-message";
    article.appendChild(element("div", "message-avatar assistant-avatar", "知"));
    var body = element("div", "message-body");
    var meta = element("div", "message-meta");
    meta.appendChild(element("strong", "", "知行助教"));
    meta.appendChild(element("span", "", "正在查阅课程资料…"));
    body.appendChild(meta);
    var bubble = element("div", "message-content");
    var typing = element("span", "typing");
    typing.appendChild(element("span"));
    typing.appendChild(element("span"));
    typing.appendChild(element("span"));
    bubble.appendChild(typing);
    body.appendChild(bubble);
    article.appendChild(body);
    scrollArea.appendChild(article);
    scrollToBottom();
    return article;
  }

  function showError(message) {
    var existing = document.querySelector(".chat-error");
    if (existing) {
      existing.remove();
    }
    var banner = element("div", "chat-error", message);
    scrollArea.appendChild(banner);
    scrollToBottom();
  }

  function updateUrl() {
    if (!conversationId) {
      return;
    }
    var url = new URL(window.location.href);
    url.searchParams.set("course", config.courseId);
    url.searchParams.set("conversation", conversationId);
    url.searchParams.delete("new");
    window.history.replaceState({}, "", url.toString());
  }

  function setSending(active) {
    isSending = active;
    sendButton.disabled = active;
    input.disabled = active;
    sendButton.querySelector("span").textContent = active ? "思考中" : "发送";
  }

  function ask(question) {
    if (isSending) {
      return;
    }
    var text = question.trim();
    if (!text) {
      return;
    }
    setSending(true);
    appendMessage("user", text);
    input.value = "";
    input.style.height = "auto";
    var typing = appendTyping();

    var payload = {
      question: text,
      course_id: config.courseId
    };
    if (conversationId) {
      payload.conversation_id = conversationId;
    }

    fetch(config.askUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken()
      },
      body: JSON.stringify(payload)
    })
      .then(function (response) {
        return response.json().then(function (data) {
          if (!response.ok) {
            throw new Error(data.error || "回答失败，请稍后重试。");
          }
          return data;
        });
      })
      .then(function (data) {
        typing.remove();
        conversationId = String(data.conversation_id);
        appendMessage("assistant", data.answer, {
          citations: data.citations,
          mode: data.mode,
          messageId: data.message_id
        });
        updateUrl();
      })
      .catch(function (error) {
        typing.remove();
        showError(error.message || "网络异常，请稍后重试。");
      })
      .finally(function () {
        setSending(false);
        input.focus();
      });
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    ask(input.value);
  });

  input.addEventListener("keydown", function (event) {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      ask(input.value);
    }
  });

  input.addEventListener("input", function () {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 150) + "px";
  });

  document.querySelectorAll(".suggestion-card").forEach(function (button) {
    button.addEventListener("click", function () {
      input.value = button.dataset.question || button.textContent.trim();
      input.dispatchEvent(new Event("input"));
      input.focus();
    });
  });

  scrollToBottom();
})();
