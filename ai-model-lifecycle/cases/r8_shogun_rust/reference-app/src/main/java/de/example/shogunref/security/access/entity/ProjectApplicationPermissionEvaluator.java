package de.example.shogunref.security.access.entity;

import de.example.shogunref.model.ProjectApplication;
import de.terrestris.shoguncore.model.User;
import de.terrestris.shoguncore.model.security.Permission;
import de.terrestris.shoguncore.security.access.entity.PersistentObjectPermissionEvaluator;

/**
 * Demonstrates the implementation of a custom permission evaluator for
 * {@link ProjectApplication}.
 * 
 * @author Nils Bühner
 *
 */
public class ProjectApplicationPermissionEvaluator<E extends ProjectApplication> extends
		PersistentObjectPermissionEvaluator<E> {
    private static final org.apache.logging.log4j.Logger R8LOG = org.apache.logging.log4j.LogManager.getLogger(ProjectApplicationPermissionEvaluator.class);


	/**
	 * Default constructor
	 */
	@SuppressWarnings("unchecked")
	public ProjectApplicationPermissionEvaluator() {
		this((Class<E>) ProjectApplication.class);
	}

	/**
	 * Constructor for subclasses
	 *
	 * @param entityClass
	 */
	protected ProjectApplicationPermissionEvaluator(Class<E> entityClass) {
		super(entityClass);
	}

	/**
	 * Always grants right to CREATE this entity.
	 */
	@Override
	public boolean hasPermission(User user, E entity, Permission permission) {

		// always grant CREATE right for this entity
		// This is just a demo!
		if (permission.equals(Permission.CREATE)) {
			R8LOG.trace("Granting CREATE for project application.");
			return true;
		}

		// call parent implementation from SHOGun-Core
		return super.hasPermission(user, entity, permission);
	}

}
