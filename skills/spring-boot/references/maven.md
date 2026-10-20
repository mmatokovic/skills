# Maven Commands

Always use the Maven wrapper (`./mvnw` on bash, `mvnw.cmd` on cmd/PowerShell) — never a local `mvn` installation.

```bash
./mvnw clean package                              # build
./mvnw test                                       # unit tests (*Test.java, *Should.java)
./mvnw test -Dtest=OrderServiceTest               # single unit test class
./mvnw verify                                     # integration tests (*IT.java)
./mvnw verify -Dit.test=OrderControllerIT         # single integration test class
./mvnw checkstyle:check                           # code style (also runs at compile)
./mvnw liquibase:validate                         # validate changesets
./mvnw dependency:tree                            # check transitive deps before adding new ones
./mvnw versions:display-dependency-updates        # available upgrades
./mvnw clean verify springdoc-openapi:generate    # generate OpenAPI docs
```
