# vim:ft=spec

%define file_prefix M4_FILE_PREFIX
%define file_ext M4_FILE_EXT
%define file_version M4_FILE_VERSION
%define file_release_tag %{nil}M4_FILE_RELEASE_TAG
%define file_release_number M4_FILE_RELEASE_NUMBER
%define file_build_number M4_FILE_BUILD_NUMBER
%define file_commit_ref M4_FILE_COMMIT_REF

Name:           dpres-access-rest-api-client
Version:        %{file_version}
Release:        %{file_release_number}%{file_release_tag}.%{file_build_number}.git%{file_commit_ref}%{?dist}
Summary:        Command-line utility anc library for the DPRES REST API
License:        LGPLv3+
URL:            https://www.digitalpreservation.fi
Source0:        %{file_prefix}-v%{file_version}%{?file_release_tag}-%{file_build_number}-g%{file_commit_ref}.%{file_ext}
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  pyproject-rpm-macros
BuildRequires:  %{py3_dist pip}
BuildRequires:  %{py3_dist setuptools}
BuildRequires:  %{py3_dist setuptools-scm}
BuildRequires:  %{py3_dist wheel}
BuildRequires:  %{py3_dist pytest}
BuildRequires:  %{py3_dist requests-mock}

%py_provides python3-dpres-access-rest-api-client

%description
Command-line utility and library for the DPRES REST API

%prep
%autosetup -n %{file_prefix}-v%{file_version}%{?file_release_tag}-%{file_build_number}-g%{file_commit_ref}

%build
export SETUPTOOLS_SCM_PRETEND_VERSION=%{file_version}
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files dpres_access_rest_api_client

%files -f %{pyproject_files}
%license LICENSE
%doc README.rst CHANGELOG.md
%{_bindir}/access-client

# TODO: For now changelog must be last, because it is generated automatically
# from git log command. Appending should be fixed to happen only after %changelog macro
%changelog

