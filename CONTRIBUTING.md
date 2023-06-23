# Contributing

![GitHub License](https://img.shields.io/github/license/PietroPasotti/theatre)
![GitHub Commit Activity](https://img.shields.io/github/commit-activity/y/PietroPasotti/theatre)
![GitHub Lines of Code](https://img.shields.io/tokei/lines/github/PietroPasotti/theatre)
![GitHub Issues](https://img.shields.io/github/issues/PietroPasotti/theatre)
![GitHub PRs](https://img.shields.io/github/issues-pr/PietroPasotti/theatre)
![GitHub Contributors](https://img.shields.io/github/contributors/PietroPasotti/theatre)
![GitHub Watchers](https://img.shields.io/github/watchers/PietroPasotti/theatre?style=social)

This documents explains the processes and practices recommended for contributing enhancements to this project.

- Generally, before developing enhancements to this project, you should
  consider [opening an issue](https://github.com/PietroPasotti/theatre/issues) explaining your use case.
- If you would like to chat with us about your use-cases or proposed implementation, you can reach us
  at [Canonical Mattermost public channel](https://chat.charmhub.io/charmhub/channels/charm-dev)
  or [Discourse](https://discourse.charmhub.io/).
- Familiarising yourself with the [Charmed Operator Framework](https://juju.is/docs/sdk) library will help you a lot
  when working on new features or bug fixes.
- All enhancements require review before being merged. Code review typically examines:
    - code quality
    - test coverage
    - user experience
- When evaluating design decisions, we optimize for the following personas, in descending order of priority:
    - charm authors and maintainers
    - the contributors to this codebase
    - juju developers
- Please help us out in ensuring easy to review branches by rebasing your pull request branch onto the `main` branch.
  This also avoids merge commits and creates a linear Git commit history.

## Developing

To set up the dependencies you can run:
`pip install -r requirements.txt`