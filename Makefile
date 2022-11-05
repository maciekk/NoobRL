ctags:
	@echo Running {exuberant-ctags,universal-ctags}.
	/usr/local/bin/ctags -R *

clean:
	@echo Cleaning up.
	rm -f tags
