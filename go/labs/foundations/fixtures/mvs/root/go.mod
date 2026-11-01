module example.invalid/mvs

go 1.25.0

require (
 example.org/a v1.0.0
 example.org/b v1.0.0
)
replace example.org/a => ../a
replace example.org/b => ../b
replace example.org/c => ../c
