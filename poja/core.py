import poja.mygit as mygit
import shutil
import poja.sed as sed
from poja.myrich import print_title, print_normal, print_banner, print_warn
from poja.version import get_version
from poja.vpcscoped import set_vpc_scoped_resources
from poja.genclients import set_gen_clients
from poja.database import set_postgres, set_sqlite
from poja.sentry import set_sentry
from poja.sonar import set_sonar
import yaml
from yaml.loader import BaseLoader
import os
from poja.myos import cd_then_exec
from pathlib import Path

GIT_URL = "https://github.com/tanjonaaa/poja"
GIT_TAG_OR_COMMIT = "4abb7c825a0420052830cf11028fe2072420d75e"

DEFAULT_GROUP_NAME = "school.hei"
DEFAULT_PACKAGE_FULL_NAME = DEFAULT_GROUP_NAME + ".poja"


def gen(
    poja_conf=None,
    app_name=None,
    region="eu-west-3",
    with_own_vpc="false",
    ssm_sg_id=None,
    ssm_subnet1_id=None,
    ssm_subnet2_id=None,
    ses_source="noreply@nowhere.com",
    with_swagger_ui="false",
    package_full_name=DEFAULT_PACKAGE_FULL_NAME,
    custom_java_repositories=None,
    custom_java_deps=None,
    custom_java_env_vars=None,
    java_facade_it="FacadeIT",
    with_gen_clients="false",
    with_database="sqlite",
    output_dir=None,
    jacoco_min_coverage="0.8",
    with_publish_to_npm_registry="false",
    ts_client_default_openapi_server_url="",
    ts_client_api_url_env_var_name="",
    frontal_memory=2048,
    worker_memory=1024,
    worker_batch=5,
    reserved_concurrent_executions_nb=None,
    with_snapstart="false",
    aurora_min_capacity=None,
    aurora_max_capacity=None,
    aurora_scale_point=None,
    aurora_sleep=300,
    aurora_auto_pause="false",
    database_non_root_username=None,
    database_non_root_password=None,
    with_sentry="false",
    with_sonar="false",
    with_codeql="false",
):
    if poja_conf is not None:
        with open(poja_conf, "r") as conf_strem:
            conf = yaml.load(conf_strem, Loader=BaseLoader)
            if get_version() != conf["cli_version"]:
                raise Exception(
                    f'You must use the poja version defined in your conf file (v{conf["cli_version"]}). Forgot to upgrade (to v{get_version()})?'
                )
            print_warn(
                "Only --poja-conf will be taken into account: all other arguments will be ignored!"
            )
            print_warn(
                "No default value will be used: explicit everything in your conf file!!"
            )
            app_name = conf["app_name"]
            region = conf["region"]
            with_own_vpc = conf["with_own_vpc"]
            ssm_sg_id = conf["ssm_sg_id"]
            ssm_subnet1_id = conf["ssm_subnet1_id"]
            ssm_subnet2_id = conf["ssm_subnet2_id"]
            ses_source = conf["ses_source"]
            with_swagger_ui = conf["with_swagger_ui"]
            package_full_name = conf["package_full_name"]
            custom_java_repositories = conf["custom_java_repositories"]
            custom_java_deps = conf["custom_java_deps"]
            custom_java_env_vars = conf["custom_java_env_vars"]
            java_facade_it = conf["java_facade_it"]
            with_gen_clients = conf["with_gen_clients"]
            with_database = conf["with_database"]
            jacoco_min_coverage = conf["jacoco_min_coverage"]
            with_publish_to_npm_registry = conf["with_publish_to_npm_registry"]
            ts_client_default_openapi_server_url = conf[
                "ts_client_default_openapi_server_url"
            ]
            ts_client_api_url_env_var_name = conf["ts_client_api_url_env_var_name"]
            frontal_memory = int(conf["frontal_memory"])
            worker_memory = int(conf["worker_memory"])
            worker_batch = int(conf["worker_batch"])
            reserved_concurrent_executions_nb = (
                int(conf["reserved_concurrent_executions_nb"])
                if conf["reserved_concurrent_executions_nb"] != "null"
                else None
            )
            with_snapstart = conf["with_snapstart"]
            aurora_min_capacity = (
                int(conf["aurora_min_capacity"])
                if conf["aurora_min_capacity"] != "null"
                else None
            )
            aurora_max_capacity = (
                int(conf["aurora_max_capacity"])
                if conf["aurora_max_capacity"] != "null"
                else None
            )
            aurora_scale_point = (
                int(conf["aurora_scale_point"])
                if conf["aurora_scale_point"] != "null"
                else None
            )
            aurora_sleep = (
                int(conf["aurora_sleep"]) if conf["aurora_sleep"] != "null" else None
            )
            aurora_auto_pause = conf["aurora_auto_pause"]
            database_non_root_username = (
                conf["database_non_root_username"]
                if conf["database_non_root_username"] != "null"
                else None
            )
            database_non_root_password = (
                conf["database_non_root_password"]
                if conf["database_non_root_password"] != "null"
                else None
            )
            with_sentry = conf["with_sentry"]
            with_codeql = conf["with_codeql"]
            with_sonar = conf["with_sonar"]

    if app_name is None:
        raise Exception(
            "app_name in conf file (or --app-name as argument) must be defined"
        )

    if output_dir is None:
        output_dir = app_name

    print_banner("POJA v" + get_version())

    print_title("Checkout base repository...")
    print_normal(f"git_url={GIT_URL}")
    print_normal(f"git_tag={GIT_TAG_OR_COMMIT}")
    tmp_dir = mygit.checkout(GIT_URL, GIT_TAG_OR_COMMIT, no_git=True)
    print_normal(f"tmp_dir={tmp_dir}")

    print_title("Handle arguments...")
    exclude = "*.jar"
    print_normal("region")
    shutil.rmtree(tmp_dir + "/mascot")
    sed.find_replace(tmp_dir, "<?aws-region>", region, exclude)
    print_normal("ses_source")
    sed.find_replace(tmp_dir, "<?aws-ses-source>", ses_source, exclude)

    if with_snapstart == "true":
        if with_database == "sqlite":
            raise Exception(
                "SQLite cannot be accessed by snapstart-enabled lambda functions"
            )
        function_snapstart = """AutoPublishAlias: live
    SnapStart:
      ApplyOn: PublishedVersions"""
        function_snapstart_java_env = ""
    else:
        function_snapstart = ""
        function_snapstart_java_env = "JAVA_TOOL_OPTIONS: -XX:+TieredCompilation -XX:TieredStopAtLevel=1 -Dspring.main.lazy-initialization=true -Dspring.data.jpa.repositories.bootstrap-mode=lazy -Dspring.datasource.max-active=5 -Dspring.datasource.max-idle=1 -Dspring.datasource.min-idle=1 -Dspring.datasource.initial-size=1"
    sed.find_replace(tmp_dir, "<?function-snapstart>", function_snapstart, exclude)
    sed.find_replace(
        tmp_dir,
        "<?function-snapstart-java-env-vars>",
        function_snapstart_java_env,
        exclude,
    )

    print_normal("frontal_memory")
    sed.find_replace(tmp_dir, "<?frontal-memory>", str(frontal_memory), exclude)
    print_normal("worker_memory")
    sed.find_replace(tmp_dir, "<?worker-memory>", str(worker_memory), exclude)
    print_normal("worker_batch")
    sed.find_replace(tmp_dir, "<?worker-batch>", str(worker_batch), exclude)
    print_normal("reserved_concurrent_executions_nb")
    if reserved_concurrent_executions_nb is None:
        sed.remove_line_by_keyword(
            f"{tmp_dir}/template.yml", "ReservedConcurrentExecutions"
        )
    else:
        sed.find_replace(
            tmp_dir,
            "<?reserved-concurrent-executions-nb>",
            str(reserved_concurrent_executions_nb),
            exclude,
        )
    print_normal("with_database")
    set_postgres(
        with_database,
        aurora_min_capacity,
        aurora_max_capacity,
        aurora_scale_point,
        aurora_sleep,
        aurora_auto_pause,
        database_non_root_username,
        database_non_root_password,
        tmp_dir,
        exclude,
    )
    set_sqlite(with_database, tmp_dir, exclude)
    print_normal("with_sentry")
    print_normal("with_sonar")
    if with_sentry == "true":
        sentry_dsn = f"/{app_name}/sentry/dsn"
        set_sentry(sentry_dsn, tmp_dir, exclude)
    if with_sonar == "true":
        set_sonar(tmp_dir, exclude)
    else:
        sed.find_replace(tmp_dir, "<?sonar-java-plugins>", "", exclude)
        sed.find_replace(tmp_dir, "<?sonar-conf>", "", exclude)
        sed.find_replace(tmp_dir, "<?sonar-env>", "", exclude)
        sed.find_replace(tmp_dir, "<?sonar-ci>", "", exclude)

    print_normal("with_own_vpc")
    set_vpc_scoped_resources(
        with_own_vpc, ssm_sg_id, ssm_subnet1_id, ssm_subnet2_id, tmp_dir, exclude
    )

    print_normal("with_gen_clients")
    set_gen_clients(with_gen_clients, tmp_dir, exclude)

    print_normal("with_swagger_ui")
    if with_swagger_ui == "true":
        springdoc_java_dep = "implementation 'org.springdoc:springdoc-openapi-ui:1.7.0'"
    else:
        springdoc_java_dep = ""
    sed.find_replace(tmp_dir, "<?java-deps-springdoc>", springdoc_java_dep, exclude)

    print_normal("package_full_name")
    sed.find_replace(tmp_dir, DEFAULT_PACKAGE_FULL_NAME, package_full_name, exclude)
    sed.find_replace(
        tmp_dir,
        DEFAULT_GROUP_NAME,
        group_name_from_package_full_name(package_full_name),
        exclude,
    )
    print_normal("custom_java_repositories")
    java_repositories = replace_with_file_content(
        tmp_dir, "<?java-repositories>", custom_java_repositories, exclude
    )
    set_package_dirs(tmp_dir, package_full_name, "main")
    set_package_dirs(tmp_dir, package_full_name, "test")
    print_normal("custom_java_deps")
    java_deps = replace_with_file_content(
        tmp_dir, "<?java-deps>", custom_java_deps, exclude
    )
    print_normal("custom_java_env_vars")
    indent = "        "
    java_env_vars = replace_with_file_content(
        tmp_dir, "<?java-env-vars>", custom_java_env_vars, exclude, joiner=indent
    )
    print_normal("java_facade_it")
    sed.find_replace(tmp_dir, "<?java-facade-it>", java_facade_it, exclude)

    print_normal("app_name")
    sed.find_replace(tmp_dir, "<?app-name>", app_name, exclude)
    print_normal("jacoco_min_coverage")
    sed.find_replace(
        tmp_dir, "<?jacoco-min-coverage>", str(jacoco_min_coverage), exclude
    )
    if with_publish_to_npm_registry == "true":
        print_normal("ts_client_default_openapi_server_url")
        sed.find_replace(
            tmp_dir,
            "<?ts-client-default-openapi-server-url>",
            ts_client_default_openapi_server_url,
            exclude,
        )
        print_normal("ts_client_api_url_env_var_name")
        sed.find_replace(
            tmp_dir,
            "<?ts-client-api-url-env-var-name>",
            ts_client_api_url_env_var_name,
            exclude,
        )
    else:
        os.remove(f"{tmp_dir}/.github/workflows/publish-client.yml")

    if with_codeql == "false":
        os.remove(f"{tmp_dir}/.github/workflows/codeql.yml")

    if with_sentry == "false":
        dirs = package_full_name.replace(".", "/")
        os.remove(f"{tmp_dir}/src/main/java/{dirs}/endpoint/SentryConf.java")
        sed.find_replace(tmp_dir, "<?sentry-test-env>", "", exclude)

    print_title("Save conf...")
    save_conf(
        tmp_dir,
        app_name,
        region,
        with_own_vpc,
        ssm_sg_id,
        ssm_subnet1_id,
        ssm_subnet2_id,
        ses_source,
        with_swagger_ui,
        package_full_name,
        java_repositories,
        java_deps,
        java_env_vars,
        java_facade_it,
        with_gen_clients,
        with_database,
        jacoco_min_coverage,
        with_publish_to_npm_registry,
        ts_client_default_openapi_server_url,
        ts_client_api_url_env_var_name,
        with_snapstart,
        frontal_memory,
        worker_memory,
        worker_batch,
        reserved_concurrent_executions_nb,
        aurora_min_capacity,
        aurora_max_capacity,
        aurora_scale_point,
        aurora_sleep,
        aurora_auto_pause,
        database_non_root_username,
        database_non_root_password,
        with_sentry,
        with_sonar,
        with_codeql,
    )
    print_normal("poja.yml")

    print_title("Rm project-specific files...")
    print_normal("README.md")
    os.remove(tmp_dir + "/README.md")
    print_normal("application.properties")
    os.remove(tmp_dir + "/src/main/resources/application.properties")
    print_normal("gradle.properties")
    os.remove(tmp_dir + "/gradle.properties")
    print_normal("LICENSE")
    os.remove(tmp_dir + "/LICENSE")

    print_title("Format...")
    cd_then_exec(tmp_dir, "format.bat", "./format.sh")

    print_title("Copy to output dir...")
    shutil.copytree(tmp_dir, output_dir, dirs_exist_ok=True)

    print_title("Client generation...")
    print_normal("doc/api.yml")
    # create doc/ and doc/api.yml if not exist
    Path(f"{output_dir}/doc").mkdir(parents=True, exist_ok=True)
    spec_path = Path(f"{output_dir}/doc/api.yml")
    if spec_path.is_file():
        print_normal("api.yml already exists, do nothing")
    else:
        spec_path.write_text("")

    print_title("... all done!")


def group_name_from_package_full_name(package_full_name):
    package_full_name_parts = get_package_full_name_parts(package_full_name)
    return package_full_name_parts[0] + "." + package_full_name_parts[1]


def save_conf(
    tmp_dir,
    app_name,
    region,
    with_own_vpc,
    ssm_sg_id,
    ssm_subnet1_id,
    ssm_subnet2_id,
    ses_source,
    with_swagger_ui,
    package_full_name,
    custom_java_repositories,
    custom_java_deps,
    custom_java_env_vars,
    java_facade_it,
    with_gen_clients,
    with_database,
    jacoco_min_coverage,
    with_publish_to_npm_registry,
    ts_client_default_openapi_server_url,
    ts_client_api_url_env_var_name,
    with_snapstart,
    frontal_memory,
    worker_memory,
    worker_batch,
    reserved_concurrent_executions_nb,
    aurora_min_capacity,
    aurora_max_capacity,
    aurora_scale_point,
    aurora_sleep,
    aurora_auto_pause,
    database_non_root_username,
    database_non_root_password,
    with_sentry,
    with_sonar,
    with_codeql,
):
    custom_java_repositories_filename = "poja-custom-java-repositories.txt"
    custom_java_deps_filename = "poja-custom-java-deps.txt"
    custom_java_env_vars_filename = "poja-custom-java-env-vars.txt"
    conf = {
        "cli_version": get_version(),
        "app_name": app_name,
        "region": region,
        "with_own_vpc": with_own_vpc,
        "ssm_sg_id": ssm_sg_id,
        "ssm_subnet1_id": ssm_subnet1_id,
        "ssm_subnet2_id": ssm_subnet2_id,
        "ses_source": ses_source,
        "with_swagger_ui": with_swagger_ui,
        "package_full_name": package_full_name,
        "custom_java_repositories": custom_java_repositories_filename,
        "custom_java_deps": custom_java_deps_filename,
        "custom_java_env_vars": custom_java_env_vars_filename,
        "java_facade_it": java_facade_it,
        "with_gen_clients": with_gen_clients,
        "with_database": with_database,
        "jacoco_min_coverage": jacoco_min_coverage,
        "with_publish_to_npm_registry": with_publish_to_npm_registry,
        "ts_client_default_openapi_server_url": ts_client_default_openapi_server_url,
        "ts_client_api_url_env_var_name": ts_client_api_url_env_var_name,
        "with_snapstart": with_snapstart,
        "frontal_memory": frontal_memory,
        "worker_memory": worker_memory,
        "worker_batch": worker_batch,
        "reserved_concurrent_executions_nb": reserved_concurrent_executions_nb,
        "aurora_min_capacity": aurora_min_capacity,
        "aurora_max_capacity": aurora_max_capacity,
        "aurora_scale_point": aurora_scale_point,
        "aurora_sleep": aurora_sleep,
        "aurora_auto_pause": aurora_auto_pause,
        "database_non_root_username": database_non_root_username,
        "database_non_root_password": database_non_root_password,
        "with_sentry": with_sentry,
        "with_sonar": with_sonar,
        "with_codeql": with_codeql,
    }
    with open(tmp_dir + "/poja.yml", "w") as conf_file:
        yaml.dump(conf, conf_file)

    print_normal(custom_java_repositories_filename)
    with open(
        f"{tmp_dir}/{custom_java_repositories_filename}", "w"
    ) as custom_java_repositories_file:
        custom_java_repositories_file.write(custom_java_repositories)

    print_normal(custom_java_deps_filename)
    with open(f"{tmp_dir}/{custom_java_deps_filename}", "w") as custom_java_deps_file:
        custom_java_deps_file.write(custom_java_deps)

    print_normal(custom_java_env_vars_filename)
    with open(
        f"{tmp_dir}/{custom_java_env_vars_filename}", "w"
    ) as custom_java_env_vars_file:
        custom_java_env_vars_file.write(
            "\n".join([s.strip() for s in custom_java_env_vars.split("\n")])
        )


def replace_with_file_content(
    project_dir, to_replace, replacement_filepath, exclude, joiner=""
):
    if replacement_filepath is None:
        content = ""
    else:
        file = open(replacement_filepath, "r")
        content = joiner.join(file.readlines())
    sed.find_replace(project_dir, to_replace, content, exclude)
    return content


def set_package_dirs(tmp_dir, package_full_name, scope):
    package_full_name_parts = get_package_full_name_parts(package_full_name)
    default_package_full_name_parts = DEFAULT_PACKAGE_FULL_NAME.split(".")
    os.rename(
        "%s/src/%s/java/%s" % (tmp_dir, scope, default_package_full_name_parts[0]),
        "%s/src/%s/java/%s" % (tmp_dir, scope, package_full_name_parts[0]),
    )
    os.rename(
        "%s/src/%s/java/%s/%s"
        % (
            tmp_dir,
            scope,
            package_full_name_parts[0],
            default_package_full_name_parts[1],
        ),
        "%s/src/%s/java/%s/%s"
        % (tmp_dir, scope, package_full_name_parts[0], package_full_name_parts[1]),
    )
    os.rename(
        "%s/src/%s/java/%s/%s/%s"
        % (
            tmp_dir,
            scope,
            package_full_name_parts[0],
            package_full_name_parts[1],
            default_package_full_name_parts[2],
        ),
        "%s/src/%s/java/%s/%s/%s"
        % (
            tmp_dir,
            scope,
            package_full_name_parts[0],
            package_full_name_parts[1],
            package_full_name_parts[2],
        ),
    )


def get_package_full_name_parts(package_full_name):
    package_full_name_parts = package_full_name.split(".")
    if len(package_full_name_parts) != 3:
        raise Exception(
            "package_full_name must exactly have 3 parts such as com.company.base"
        )
    return package_full_name_parts
