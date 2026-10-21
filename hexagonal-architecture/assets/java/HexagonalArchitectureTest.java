package com.example.app;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;
import static com.tngtech.archunit.library.dependencies.SlicesRuleDefinition.slices;

import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;

/**
 * ArchUnit template for a Java repo with hexagonal architecture.
 *
 * Copy it to src/test/java/com/example/app/ and adjust:
 *   - The packages in @AnalyzeClasses to the root package.
 *   - ..core.. and ..adapters.. to the real names.
 *   - The list of technology packages that the core must not import.
 *
 * Test dependency: com.tngtech.archunit:archunit-junit5
 * Run: mvn test -Dtest=HexagonalArchitectureTest
 */
@AnalyzeClasses(
    packages = "com.example.app",
    importOptions = ImportOption.DoNotIncludeTests.class)
class HexagonalArchitectureTest {

    @ArchTest
    static final ArchRule core_without_adapters =
        noClasses()
            .that()
            .resideInAPackage("..core..")
            .should()
            .dependOnClassesThat()
            .resideInAnyPackage("..adapters..");

    @ArchTest
    static final ArchRule core_without_technology =
        noClasses()
            .that()
            .resideInAPackage("..core..")
            .should()
            .dependOnClassesThat()
            .resideInAnyPackage(
                "org.springframework..",
                "jakarta..",
                "javax.persistence..",
                "java.sql..",
                "java.net.http..",
                "org.hibernate..",
                "com.amazonaws..",
                "software.amazon.awssdk..",
                "com.google.cloud..",
                "com.azure..");

    // Each slice is a folder under adapters: driving and driven.
    // If each adapter lives in its own subfolder, use
    // "com.example.app.adapters.(*).(*).." to isolate them from each other too.
    @ArchTest
    static final ArchRule adapters_independent =
        slices()
            .matching("com.example.app.adapters.(*)..")
            .should()
            .notDependOnEachOther();
}
