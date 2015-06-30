# ComboCode Documentation
This branch was created to provide the online documentation for ComboCode, available at: <a href="https://robinlombaert.github.io/ComboCode"> robinlombaert.github.io/ComboCode</a>

To create the documentation and maintain it, follow the procedure outlined 
<a href="https://help.github.com/articles/creating-project-pages-manually/"> here</a>. Apply it to a subfolder of the 
ComboCode home folder in your local repository, e.g. `~/ComboCode/doc/`

Epydoc is used to create the .html source in the procedure described above:

`epydoc ~/ComboCode/ -o ~/ComboCode/doc/ --html --graph all -v`

Once created, continue to follow the procedure to commit and push the documentation to the gh-pages branch on GitHub.
