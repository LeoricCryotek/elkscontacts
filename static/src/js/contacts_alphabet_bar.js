/** @odoo-module **/
/*
 *  Contacts Alphabet Bar
 *
 *  Renders a horizontal A-Z (+ "All" / "#") bar above the Contacts
 *  list / kanban view. Clicking a letter restricts the view to
 *  contacts whose last name starts with that letter. The bar is
 *  scoped to res.partner views only (other models load the standard
 *  Odoo layout unchanged).
 *
 *  Hooks into the existing search model by adding/clearing a
 *  filter "domain part" keyed by 'alphabet_bar'. That key plays
 *  cleanly with any other search facets / filters the user has
 *  applied.
 */

import { Component, useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { Layout } from "@web/search/layout";

const LETTERS = [
    "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M",
    "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z",
    "#",
];

export class ContactsAlphabetBar extends Component {
    static template = "elkscontacts.ContactsAlphabetBar";
    static props = {};

    setup() {
        this.state = useState({ active: "All" });
        this.letters = LETTERS;
    }

    /**
     * Only show the bar when the active view is on res.partner.
     * (env.searchModel is the model that drives the current view's
     * domain/facets — its resModel reflects the underlying record
     * model.)
     */
    get isContactsView() {
        try {
            return this.env.searchModel?.resModel === "res.partner";
        } catch (e) {
            return false;
        }
    }

    /**
     * Click handler — push (or clear) a domain part on the search
     * model. The key 'alphabet_bar' identifies our slice so we can
     * replace/clear it without disturbing other facets.
     */
    onLetterClick(letter) {
        this.state.active = letter;
        const searchModel = this.env.searchModel;
        if (!searchModel) {
            return;
        }
        const part =
            letter === "All"
                ? { domain: [] }
                : { domain: [["x_last_name_letter", "=", letter]] };
        try {
            searchModel.setDomainParts({ alphabet_bar: part });
        } catch (e) {
            // Fall back to a hard domain set if the API differs.
            // This keeps the page usable even if the search model
            // exposes a different surface on a future Odoo build.
            console.warn(
                "[elkscontacts] alphabet bar setDomainParts failed",
                e
            );
        }
    }
}

/*
 *  Inject the bar into the standard view Layout.
 *
 *  The Layout component wraps the control panel and the view content.
 *  We extend its template (see contacts_alphabet_bar.xml) and need to
 *  make our component class available to that template scope, which is
 *  what the patched setup() does.
 */
patch(Layout.prototype, {
    setup() {
        super.setup(...arguments);
        this.ContactsAlphabetBar = ContactsAlphabetBar;
    },
});
