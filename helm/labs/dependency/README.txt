Dependency tests COPY chart and lab-labels into a temporary tree.
They add file://../lab-labels to the copy, update its Chart.lock, remove only
that copy's charts/, run dependency build and compare rendered objects.
The persistent main chart is never reset or changed by this test.
