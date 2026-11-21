package de.example.shogunref.init;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;

import de.terrestris.shoguncore.init.ContentInitializer;

/**
 * This is a demo class that demonstrates how the SHOGun-Core
 * {@link ContentInitializer} can be extended.
 *
 * @author Nils Bühner
 *
 */
public class ProjectContentInitializer extends ContentInitializer {
    private static final org.apache.logging.log4j.Logger R8LOG = org.apache.logging.log4j.LogManager.getLogger(ProjectContentInitializer.class);


	/**
	 * Flag symbolizing if something should be initialized on startup
	 */
	@Autowired
	@Qualifier("projectInitEnabled")
	private Boolean projectInitEnabled;

	@Override
	public void initializeDatabaseContent() {

		super.initializeDatabaseContent();

		if(projectInitEnabled){
			// init project specific stuff...
			R8LOG.info("Initializing project specific stuff...");
		}

	}

}
