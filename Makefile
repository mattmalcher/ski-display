REMOTE := matt@192.168.8.133
REMOTE_DIR := ~/display

.PHONY: deploy

deploy:
	rsync -av --exclude='config.json' display/ $(REMOTE):$(REMOTE_DIR)/
	rsync -av pyproject.toml uv.lock $(REMOTE):$(REMOTE_DIR)/
	ssh $(REMOTE) "cd $(REMOTE_DIR) && ~/.local/bin/uv sync --frozen --no-install-package lgpio && sudo systemctl restart display display-web"
